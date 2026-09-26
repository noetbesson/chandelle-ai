from dataclasses import replace
import importlib
import json
import os
import subprocess
import wave

import httpx
import pytest

from backend.integrations.reels.config import Settings
from backend.integrations.reels.errors import ReelError
from backend.integrations.reels.extract_audio import extract_audio
from backend.integrations.reels.transcribe_gradium import transcribe

media = importlib.import_module("backend.integrations.reels.extract_audio")


def settings(tmp_path):
    return replace(Settings(), work_dir=tmp_path, allow_live=True, gradium_api_key="test-key")


def wav_file(path):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 1600)
    return path


def probe(audio=True, duration=1, width=320):
    return json.dumps({"format": {"duration": str(duration)}, "streams": [
        {"codec_type": "video", "width": width, "height": 240},
        *([{"codec_type": "audio"}] if audio else [])]}).encode()


def test_no_audio_preserves_source(tmp_path, monkeypatch):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"fixture")
    monkeypatch.setattr(media, "_run", lambda *a, **k: probe(False))
    assert extract_audio(source, settings=settings(tmp_path)) is None
    assert source.read_bytes() == b"fixture"


def test_ffmpeg_python_command_and_wav(tmp_path, monkeypatch):
    source = tmp_path / "input.mov"
    source.write_bytes(b"fixture")
    commands = []
    def run(command, *, output=False):
        commands.append(command)
        if output:
            return probe()
        wav_file(tmp_path / "audio.wav")
        return b""
    monkeypatch.setattr(media, "_run", run)
    result = extract_audio(source, settings=settings(tmp_path))
    assert result == tmp_path / "audio.wav"
    assert "file,pipe" in commands[0] and "file,pipe" in commands[1]
    assert "pcm_s16le" in commands[1] and "16000" in commands[1]
    assert "-nostdin" in commands[1] and "-n" in commands[1]


@pytest.mark.parametrize("metadata", [probe(duration=181), probe(width=8000), b"not json", probe(duration="nan")])
def test_bad_video_metadata_rejected(tmp_path, monkeypatch, metadata):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"fixture")
    monkeypatch.setattr(media, "_run", lambda *a, **k: metadata)
    with pytest.raises(ReelError):
        extract_audio(source, settings=settings(tmp_path))


def test_path_escape_rejected(tmp_path):
    with pytest.raises(ReelError, match="dossier de travail"):
        extract_audio(tmp_path.parent / "other.mp4", settings=settings(tmp_path))


def test_subprocess_timeout_safe(monkeypatch):
    def fail(*args, **kwargs):
        assert kwargs["shell"] is False and kwargs["timeout"] == 40
        raise subprocess.TimeoutExpired("private command", 40)
    monkeypatch.setattr(media.subprocess, "run", fail)
    with pytest.raises(ReelError) as error:
        media._run(["ffmpeg"])
    assert error.value.code == "MEDIA_TIMEOUT"
    assert "private" not in str(error.value)


def test_gradium_raw_wav_ndjson_contract(tmp_path):
    audio = wav_file(tmp_path / "audio.wav")
    def handler(request):
        assert str(request.url).startswith("https://api.gradium.ai/api/post/speech/asr?")
        assert json.loads(request.url.params["json_config"]) == {"language": "any"}
        assert request.headers["x-api-key"] == "test-key"
        assert request.headers["content-type"] == "audio/wav"
        assert request.content.startswith(b"RIFF")
        return httpx.Response(200, text='{"type":"text","text":"Un atelier"}\n{"type":"text","text":"de poterie"}\n{"type":"end_text"}\n')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert transcribe(audio, settings=settings(tmp_path), client=client) == "Un atelier de poterie"


@pytest.mark.parametrize("response", [httpx.Response(503, text="PRIVATE PROVIDER ERROR"),
    httpx.Response(200, text='{"type":"text","text":"partial"}\n{"type":"error","message":"PRIVATE"}'),
    httpx.Response(200, text="invalid JSON"), httpx.Response(302, headers={"location": "https://evil.test"}),
    httpx.Response(200, content=b"x" * 1_048_577)])
def test_gradium_failure_empty_private_logs(tmp_path, caplog, response):
    audio = wav_file(tmp_path / "audio.wav")
    with httpx.Client(transport=httpx.MockTransport(lambda req: response)) as client:
        assert transcribe(audio, settings=settings(tmp_path), client=client) == ""
    assert "PRIVATE" not in caplog.text and "test-key" not in caplog.text


def test_disabled_missing_audio_and_host_never_call(tmp_path):
    def forbidden(request):
        pytest.fail("No request allowed")
    audio = wav_file(tmp_path / "audio.wav")
    cfg = settings(tmp_path)
    with httpx.Client(transport=httpx.MockTransport(forbidden)) as client:
        for candidate in [replace(cfg, allow_live=False), replace(cfg, gradium_api_key=""),
                          replace(cfg, gradium_stt_url="https://evil.test/api/post/speech/asr")]:
            assert transcribe(audio, settings=candidate, client=client) == ""
        assert transcribe(None, settings=cfg, client=client) == ""


@pytest.mark.parametrize("audio", [True, False])
def test_real_ffmpeg_local_synthetic(tmp_path, audio):
    cfg = settings(tmp_path)
    if not cfg.ffmpeg_path.is_file() or not cfg.ffprobe_path.is_file():
        pytest.skip("Local FFmpeg tools are not installed")
    source = tmp_path / "input.mp4"
    command = [str(cfg.ffmpeg_path), "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=10"]
    if audio:
        command += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000"]
    command += ["-t", "1", "-c:v", "mpeg4", "-threads", "1", str(source)]
    subprocess.run(command, timeout=20, check=True, capture_output=True,
                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    result = extract_audio(source, settings=cfg)
    assert source.is_file()
    if audio:
        assert result is not None
        with wave.open(str(result)) as wav:
            assert wav.getframerate() == 16000 and wav.getnchannels() == 1
            assert 0.8 < wav.getnframes() / wav.getframerate() < 1.2
    else:
        assert result is None
