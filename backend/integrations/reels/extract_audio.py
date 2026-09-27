"""Bounded, local-only media extraction. The caller owns temporary-file cleanup."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import wave

import ffmpeg

from .config import Settings
from .errors import ReelError


def private_file(path: Path, settings: Settings) -> Path:
    root = settings.work_dir.absolute()
    candidate = path.absolute()
    if not candidate.is_relative_to(root):
        raise ReelError("MEDIA_PATH", "Le fichier doit être dans le dossier de travail.")
    for part in [candidate, *candidate.parents]:
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ReelError("MEDIA_PATH", "Les liens de fichiers ne sont pas acceptés.")
    if not candidate.is_file() or not candidate.resolve().is_relative_to(root.resolve()):
        raise ReelError("MEDIA_PATH", "Fichier temporaire introuvable.")
    if not 0 < candidate.stat().st_size <= settings.max_bytes:
        raise ReelError("MEDIA_SIZE", "Le fichier dépasse la taille autorisée.", 413)
    return candidate


def _run(arguments: list[str], *, output: bool = False) -> bytes:
    try:
        result = subprocess.run(
            arguments, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if output else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=40, check=True, shell=False,
            env={key: value for key, value in os.environ.items()
                 if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP"}},
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return result.stdout if output else b""
    except FileNotFoundError as exc:
        raise ReelError("FFMPEG_MISSING", "FFmpeg ou ffprobe doit être installé.", 503) from exc
    except subprocess.TimeoutExpired as exc:
        raise ReelError("MEDIA_TIMEOUT", "Le traitement vidéo a dépassé 40 secondes.", 408) from exc
    except (subprocess.CalledProcessError, OSError) as exc:
        raise ReelError("MEDIA_INVALID", "Le fichier vidéo ne peut pas être lu.") from exc


def extract_audio(video_path: Path, *, settings: Settings | None = None) -> Path | None:
    cfg = settings or Settings.load()
    source = private_file(video_path, cfg)
    if source.suffix.lower() not in {".mp4", ".mov"}:
        raise ReelError("MEDIA_FORMAT", "Formats acceptés : MP4 et MOV.", 415)
    probe = _run([
        str(cfg.ffprobe_path), "-v", "error", "-protocol_whitelist", "file,pipe",
        "-f", "mov",
        "-show_entries", "format=duration:stream=codec_type,width,height",
        "-of", "json", str(source),
    ], output=True)
    try:
        if len(probe) > 65536:
            raise ValueError("probe limit")
        info = json.loads(probe)
        duration = float(info["format"]["duration"])
        streams = info["streams"]
        video = next(s for s in streams if s["codec_type"] == "video")
        width, height = int(video["width"]), int(video["height"])
        if not math.isfinite(duration) or not 0 < duration <= cfg.max_seconds:
            raise ReelError("MEDIA_DURATION", "La vidéo dépasse la durée autorisée.")
        if not 0 < width <= 4096 or not 0 < height <= 4096 or width * height > 12_000_000:
            raise ReelError("MEDIA_DIMENSIONS", "Les dimensions de la vidéo sont trop grandes.")
    except (ValueError, TypeError, KeyError, StopIteration) as exc:
        raise ReelError("MEDIA_INVALID", "La vidéo ne contient pas de piste exploitable.") from exc
    if not any(s.get("codec_type") == "audio" for s in streams):
        return None
    destination = source.parent / "audio.wav"
    # A staged job has its own private directory; never overwrite a preexisting path.
    if destination.exists() or destination.is_symlink():
        raise ReelError("MEDIA_OUTPUT_EXISTS", "Un fichier audio existe déjà pour ce traitement.")
    stream = ffmpeg.input(str(source), format="mov", protocol_whitelist="file,pipe")
    stream = ffmpeg.output(stream.audio, str(destination), format="wav", acodec="pcm_s16le",
                           ar=16000, ac=1, t=cfg.max_seconds, threads=1)
    arguments = ffmpeg.compile(stream, cmd=str(cfg.ffmpeg_path))
    arguments[1:1] = ["-nostdin", "-v", "error", "-n"]
    try:
        _run(arguments)
        private_file(destination, cfg)
        with wave.open(str(destination), "rb") as wav:
            if (wav.getnchannels(), wav.getframerate(), wav.getsampwidth()) != (1, 16000, 2):
                raise ReelError("MEDIA_INVALID", "L'extraction audio n'est pas au format attendu.")
        return destination
    except Exception:
        destination.unlink(missing_ok=True)
        raise
