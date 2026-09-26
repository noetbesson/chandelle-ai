"""Replaceable boundaries for integrations outside the offline core path."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


class DustAdapter(Protocol):
    def explain_plan(self, context: dict[str, Any]) -> str: ...


class PipelexAdapter(Protocol):
    def run_workflow(self, context: dict[str, Any]) -> dict[str, Any]: ...


class OpenAIAdapter(Protocol):
    def extract_constraints(self, text: str) -> dict[str, Any]: ...


class BookingAdapter(Protocol):
    def handoff(self, booking_url: str | None) -> dict[str, Any]: ...


class LocalBookingHandoff:
    def handoff(self, booking_url: str | None) -> dict[str, Any]:
        return {"booking_url": booking_url, "human_confirmation_required": True}


class LocalConnectorSignals:
    """Optional normalized D fixture, kept out of the default recommendation path."""

    def __init__(self, path: Path | None = None):
        self.path = path or Path(__file__).resolve().parents[2] / "mocks" / "D" / "signals.json"

    def for_couple(self, couple_id: str) -> list[dict[str, Any]]:
        records = json.loads(self.path.read_text(encoding="utf-8"))
        return [record for record in records if record["couple_id"] == couple_id]
