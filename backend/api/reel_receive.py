from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import shutil
from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4, UUID

from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.requests import Request

from backend.integrations.reels.config import Settings
from backend.integrations.reels.errors import ReelError
from backend.integrations.reels.models import source_url


@dataclass(frozen=True)
class Received:
    job_id: str
    video_path: Path
    caption: str | None
    source_url: str | None
    fingerprint: str
    signal_at: str | None
    share_with_couple: bool
    cloud_consent: bool
    processing: str = "legacy"


def cleanup(job_id: str, settings: Settings) -> None:
    UUID(job_id)
    root = settings.work_dir.resolve()
    target = root / job_id
    if target.is_symlink() or not target.resolve().is_relative_to(root):
        raise ReelError("PATH", "Chemin de travail refusé.")
    if target.exists():
        shutil.rmtree(target)


def canonical_url(value: str) -> str:
    u = urlsplit(value)
    pairs = [(k, v) for k, v in parse_qsl(u.query) if not k.lower().startswith("utm_") and k.lower() not in {"igsh", "igshid", "fbclid", "gclid", "_t", "_r", "share_link_id", "share_item_id"}]
    return urlunsplit((u.scheme, u.netloc.lower().removeprefix("www."), u.path.rstrip("/"), urlencode(sorted(pairs)), ""))


async def receive(request: Request, settings: Settings) -> Received:
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        raise ReelError("FORMAT", "Un formulaire multipart est requis.", 415)
    maximum = settings.max_bytes + 65536
    try:
        if int(request.headers.get("content-length", "0")) > maximum:
            raise ReelError("SIZE", "Vidéo trop volumineuse (32 MiB maximum par défaut).", 413)
    except ValueError:
        raise ReelError("VALIDATION", "Taille de requête invalide.", 400) from None

    async def bounded_stream() -> AsyncGenerator[bytes, None]:
        total = 0
        async for part in request.stream():
            total += len(part)
            if total > maximum:
                raise ReelError("SIZE", "Vidéo trop volumineuse.", 413)
            yield part

    parser = MultiPartParser(request.headers, bounded_stream(), max_files=1, max_fields=8, max_part_size=10000)
    # Bounded in-memory parser: no spool to a system temp folder outside this copy.
    parser.spool_max_size = maximum + 1
    try:
        form = await asyncio.wait_for(parser.parse(), timeout=30)
    except (MultiPartException, asyncio.TimeoutError, ReelError) as error:
        for handle in parser._files_to_close_on_error:
            handle.close()
        if isinstance(error, ReelError):
            raise
        if isinstance(error, asyncio.TimeoutError):
            raise ReelError("TIMEOUT", "Envoi trop lent. Réessayez.", 408) from None
        raise ReelError("FORMAT", "Formulaire ou fichier non pris en charge.", 415) from None
    job_id = str(uuid4())
    try:
        allowed = {"video", "caption", "source_url", "consent", "cloud_consent", "share_with_couple", "signal_at", "processing"}
        keys = [key for key, _ in form.multi_items()]
        if len(keys) != len(set(keys)) or set(keys) - allowed:
            raise ReelError("VALIDATION", "Champ inconnu ou répété.", 422)

        def text(key: str) -> str:
            value = form.get(key, "")
            if not isinstance(value, str):
                raise ReelError("VALIDATION", "Un champ texte contient un fichier.", 422)
            return value.strip()

        def flag(key: str) -> bool:
            value = text(key)
            if value not in {"", "true", "false"}:
                raise ReelError("VALIDATION", "Consentement invalide.", 422)
            return value == "true"

        if not flag("consent"):
            raise ReelError("CONSENT", "Confirmez votre autorisation d'utiliser ce fichier.", 422)
        video = form.get("video")
        if not isinstance(video, UploadFile) or not video.filename:
            raise ReelError("VIDEO", "Ajoutez un fichier vidéo MP4 ou MOV.", 422)
        extension = Path(video.filename).suffix.lower()
        if extension not in {".mp4", ".mov"} or video.content_type not in {"video/mp4", "video/quicktime"}:
            raise ReelError("FORMAT", "Formats acceptés : MP4 et MOV.", 415)
        if not video.size or video.size > settings.max_bytes:
            raise ReelError("SIZE", "Fichier vide ou trop volumineux.", 413)
        signature = await video.read(32)
        if len(signature) < 12 or signature[4:8] != b"ftyp":
            raise ReelError("FORMAT", "Le contenu ne correspond pas à une vidéo MP4/MOV.", 415)
        await video.seek(0)
        caption = text("caption") or None
        if caption and len(caption) > 10000:
            raise ReelError("SIZE", "Légende limitée à 10 000 caractères.", 413)
        try:
            url = source_url(text("source_url") or None)
            stamp = text("signal_at") or None
            if stamp:
                date = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                if date.tzinfo is None or date > datetime.now(timezone.utc):
                    raise ValueError("Date du signal invalide.")
                stamp = date.astimezone(timezone.utc).isoformat()
        except ValueError:
            raise ReelError("VALIDATION", "Lien HTTPS ou date d'origine invalide.", 422) from None
        processing = text("processing") or "legacy"
        if processing not in {"legacy", "standard"}:
            raise ReelError("VALIDATION", "Mode de traitement invalide.", 422)
        cloud = flag("cloud_consent")
        shared = flag("share_with_couple")
        directory = settings.work_dir.resolve() / job_id
        directory.mkdir(parents=True, mode=0o700)
        path = directory / ("input" + extension)
        digest = sha256()
        with path.open("xb") as output:
            while chunk := await video.read(65536):
                output.write(chunk)
                digest.update(chunk)
        fingerprint = sha256(canonical_url(url).encode()).hexdigest() if url else digest.hexdigest()
        return Received(job_id, path, caption, url, fingerprint, stamp, shared, cloud, processing)
    except BaseException:
        cleanup(job_id, settings)
        raise
    finally:
        await form.close()
