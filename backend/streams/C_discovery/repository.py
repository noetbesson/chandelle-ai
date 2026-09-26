"""Provider boundary and local, read-only Paris listing repository."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .models import ActivityListing


DEFAULT_FIXTURE = Path(__file__).with_name("paris_activities.json")


class ActivityRepository(Protocol):
    def list_activities(self) -> list[ActivityListing]: ...


class LocalActivityRepository:
    def __init__(self, path: Path = DEFAULT_FIXTURE):
        self.path = Path(path)

    def list_activities(self) -> list[ActivityListing]:
        listings = [ActivityListing.model_validate(item)
                    for item in json.loads(self.path.read_text(encoding="utf-8"))]
        ids = [item.candidate.id for item in listings]
        if len(ids) != len(set(ids)):
            raise ValueError("Activity repository contains duplicate IDs")
        return listings
