"""Explicit opt-in settings; no automatic .env loading or external account discovery."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
import os

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    work_dir: Path = ROOT / '.runtime' / 'reels'
    ffmpeg_path: Path = ROOT / '.runtime' / 'tools' / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
    ffprobe_path: Path = ROOT / '.runtime' / 'tools' / ('ffprobe.exe' if os.name == 'nt' else 'ffprobe')
    max_bytes: int = 32 * 1024 * 1024
    max_seconds: int = 180
    gradium_stt_url: str = 'https://api.gradium.ai/api/post/speech/asr'
    gradium_api_key: str = field(default='', repr=False)
    pipelex_api_key: str = field(default='', repr=False)
    openai_api_key: str = field(default='', repr=False)
    openai_model: str = 'gpt-4o'
    normalization_backend: Literal['local','openai','pipelex'] = 'local'
    allow_live: bool = False

    @classmethod
    def load(cls) -> 'Settings':
        mode = os.getenv('REELS_NORMALIZATION_BACKEND', 'local')
        if mode not in {'local','openai','pipelex'}:
            raise ValueError('REELS_NORMALIZATION_BACKEND invalide')
        base = cls()
        return cls(ffmpeg_path=Path(os.getenv('REELS_FFMPEG_PATH') or base.ffmpeg_path),
                   ffprobe_path=Path(os.getenv('REELS_FFPROBE_PATH') or base.ffprobe_path),
                   normalization_backend=mode,
                   openai_model=os.getenv('REELS_OPENAI_MODEL') or os.getenv('OPENAI_MODEL') or 'gpt-4o',
                   openai_api_key=os.getenv('OPENAI_API_KEY',''),
                   gradium_api_key=os.getenv('GRADIUM_API_KEY',''),
                   pipelex_api_key=os.getenv('PIPELEX_API_KEY',''),
                   allow_live=os.getenv('REELS_LIVE_ENABLED') == '1')
