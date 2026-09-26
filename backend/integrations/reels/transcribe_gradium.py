"""Gradium REST STT. Failures are nonfatal and never logged with private content."""
from __future__ import annotations

import json
import logging
from pathlib import Path
import time
from urllib.parse import urlsplit
import wave

import httpx

from .config import Settings
from .extract_audio import private_file

logger = logging.getLogger(__name__)


def transcribe(audio_path: Path | None, *, settings: Settings | None = None,
               client: httpx.Client | None = None) -> str:
    cfg = settings or Settings.load()
    if audio_path is None:
        return ""
    if not cfg.allow_live or not cfg.gradium_api_key:
        logger.info("gradium_stt_unconfigured_or_disabled")
        return ""
    owned = client is None
    transport = client
    try:
        url = urlsplit(cfg.gradium_stt_url)
        if (url.scheme != "https" or url.hostname not in {
                "api.gradium.ai", "eu.api.gradium.ai", "us.api.gradium.ai"}
                or url.path != "/api/post/speech/asr" or url.username or url.password
                or url.port not in (None, 443) or url.query or url.fragment):
            logger.warning("gradium_stt_endpoint_refused")
            return ""
        path = private_file(audio_path, cfg)
        with wave.open(str(path), "rb") as wav:
            if (wav.getnchannels(), wav.getframerate(), wav.getsampwidth()) != (1, 16000, 2):
                logger.warning("gradium_stt_invalid_wav")
                return ""
            if wav.getnframes() == 0 or wav.getnframes() / 16000 > cfg.max_seconds:
                return ""
        transport = transport or httpx.Client(timeout=60, follow_redirects=False, trust_env=False)
        started = time.monotonic()
        with transport.stream(
            "POST", cfg.gradium_stt_url,
            params={"json_config": json.dumps({"language": "any"})},
            headers={"x-api-key": cfg.gradium_api_key, "Content-Type": "audio/wav"},
            content=path.read_bytes(), timeout=60, follow_redirects=False,
        ) as response:
            if response.status_code != 200:
                logger.warning("gradium_stt_http_status_%s", response.status_code)
                return ""
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > 1_048_576 or time.monotonic() - started > 90:
                    logger.warning("gradium_stt_response_limit")
                    return ""
            texts: list[str] = []
            for line in body.decode("utf-8").splitlines():
                if not line.strip():
                    continue
                event = json.loads(line)
                if not isinstance(event, dict) or event.get("type") == "error":
                    logger.warning("gradium_stt_provider_error")
                    return ""
                if event.get("type") == "text":
                    if not isinstance(event.get("text"), str):
                        return ""
                    texts.append(event["text"])
            text = " ".join(texts).strip()
            if len(text) > 60000:
                logger.warning("gradium_stt_transcript_limit")
                return ""
            return text
    except Exception:
        # Exception messages can contain a URL, request headers or a provider response.
        logger.warning("gradium_stt_failed_caption_fallback")
        return ""
    finally:
        if owned and transport is not None:
            transport.close()
