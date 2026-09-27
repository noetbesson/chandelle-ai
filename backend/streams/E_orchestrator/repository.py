"""Optional local JSON candidate source; no network access."""

import json
from pathlib import Path

from .models import CandidateActivity


DEFAULT_DATA = None


def load_candidates(path: Path | None = None) -> list[CandidateActivity]:
    if path is None:return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Candidate repository must contain a JSON list")
    return [CandidateActivity.model_validate(item) for item in data]

