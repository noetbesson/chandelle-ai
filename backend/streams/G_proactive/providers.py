"""Optional proactive provider boundaries; local mode never calls remote providers."""
from typing import Protocol
from backend.streams.E_orchestrator.models import TimeWindow

class AvailabilityProvider(Protocol):
    def next_common_slot(self, couple_id: str) -> TimeWindow: ...

class WeatherProvider(Protocol):
    def conditions(self, latitude: float, longitude: float, window: TimeWindow) -> dict: ...

class CatalogUpdateProvider(Protocol):
    def new_candidate_ids(self, since: str) -> list[str]: ...
