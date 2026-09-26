"""Deterministic language boundary and feedback loop."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from backend.api.pipeline import CoreRequest, DatePipeline, PlanResult
from backend.streams.B_memory import (CoupleProfile, DateHistoryEntry, FeedbackRecord,
                                      ProfileUpdate, SelectionRecord)
from backend.streams.C_discovery import DiscoveryConstraints
from backend.streams.E_orchestrator.models import TimeWindow


class ParsedConstraints(BaseModel):
    budget: float | None = Field(default=None, ge=0)
    preferred_tag: str | None = None
    excluded_tags: list[str] = Field(default_factory=list)


class ConstraintParser(Protocol):
    def parse(self, text: str) -> ParsedConstraints: ...


class MockConstraintParser:
    """Small documented vocabulary; future OpenAI adapters implement ConstraintParser."""

    tags = ("jazz", "cinema", "art", "museum", "wine", "comedy", "outdoors", "food")

    def parse(self, text: str) -> ParsedConstraints:
        lowered = text.casefold()
        match = re.search(r"\b(?:under|below|budget(?: of)?)\s*(?:€\s*)?(\d+(?:\.\d+)?)", lowered)
        budget = float(match.group(1)) if match else None
        excluded = [tag for tag in self.tags if re.search(rf"\b(?:no|avoid)\s+{tag}\b", lowered)]
        preferred = next((tag for tag in self.tags
                          if tag not in excluded and re.search(rf"\b{tag}\b", lowered)), None)
        return ParsedConstraints(budget=budget, preferred_tag=preferred, excluded_tags=excluded)


class DateRequest(BaseModel):
    couple_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    time_window: TimeWindow | None = None
    budget: float | None = Field(default=None, ge=0)
    categories: list[str] = Field(default_factory=list)
    required_tags: list[str] = Field(default_factory=list)
    excluded_tags: list[str] = Field(default_factory=list)
    profile_update: ProfileUpdate | None = None
    max_plans: int = Field(default=3, ge=1, le=3)


class FeedbackRequest(BaseModel):
    couple_id: str = Field(min_length=1)
    date_plan_id: str = Field(min_length=1)
    rating: int | None = Field(default=None, ge=1, le=5)
    sentiment: Literal["positive", "neutral", "negative"] | None = None
    liked_tags: list[str] = Field(default_factory=list)
    disliked_tags: list[str] = Field(default_factory=list)
    text: str | None = None
    decision: Literal["selected", "rejected"] | None = None
    occurred_at: datetime | None = None
    activities: list[str] = Field(default_factory=list)


def default_availability(now: datetime | None = None) -> TimeWindow:
    """Mock A availability: next Friday 19:00–23:15, Europe/Paris."""
    current = now or datetime.now(ZoneInfo("Europe/Paris"))
    if current.tzinfo is None:
        current = current.replace(tzinfo=ZoneInfo("Europe/Paris"))
    days = (4 - current.weekday()) % 7
    start = current.replace(hour=19, minute=0, second=0, microsecond=0) + timedelta(days=days)
    if start <= current:
        start += timedelta(days=7)
    return TimeWindow(start=start, end=start.replace(hour=23, minute=15))


class ConversationService:
    def __init__(self, pipeline: DatePipeline, parser: ConstraintParser | None = None):
        self.pipeline = pipeline
        self.parser = parser or MockConstraintParser()

    def request_date(self, request: DateRequest) -> PlanResult:
        parsed = self.parser.parse(request.text)
        budget = request.budget if request.budget is not None else parsed.budget
        tags = request.required_tags or ([parsed.preferred_tag] if parsed.preferred_tag else [])
        rules = DiscoveryConstraints(include_types=request.categories, required_tags=tags,
                                     excluded_tags=[*parsed.excluded_tags, *request.excluded_tags],
                                     max_total_budget=budget)
        return self.pipeline.plan(CoreRequest(couple_id=request.couple_id,
                                              time_window=request.time_window or default_availability(),
                                              profile_update=request.profile_update,
                                              discovery=rules, max_plans=request.max_plans))

    def submit_feedback(self, request: FeedbackRequest) -> CoupleProfile:
        memory = self.pipeline.memory
        if request.decision is not None:
            memory.record_selection(request.couple_id, SelectionRecord(
                date_plan_id=request.date_plan_id, decision=request.decision))
        if request.occurred_at is not None:
            memory.record_date(request.couple_id, DateHistoryEntry(
                date_plan_id=request.date_plan_id, occurred_at=request.occurred_at,
                activities=request.activities))
        return memory.ingest_feedback(request.couple_id, FeedbackRecord(
            date_plan_id=request.date_plan_id, rating=request.rating,
            sentiment=request.sentiment, liked_tags=request.liked_tags,
            disliked_tags=request.disliked_tags, text=request.text))

    def memory_snapshot(self, couple_id: str) -> CoupleProfile:
        return self.pipeline.memory.get_snapshot(couple_id)
