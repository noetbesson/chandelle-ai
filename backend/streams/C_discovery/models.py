"""Provisional discovery input and provider-normalized listing models."""

from pydantic import BaseModel, Field

from backend.streams.E_orchestrator.models import CandidateActivity


class ActivityListing(BaseModel):
    candidate: CandidateActivity
    # Python weekdays: Monday=0, Sunday=6. Empty means unavailable.
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)))


class DiscoveryConstraints(BaseModel):
    include_types: list[str] = Field(default_factory=list)
    required_tags: list[str] = Field(default_factory=list)
    excluded_tags: list[str] = Field(default_factory=list)
    max_total_budget: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    limit: int = Field(default=30, ge=1, le=100)
