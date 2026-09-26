"""Deterministic G trigger over mock availability, B memory and C candidates."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from backend.api.pipeline import CoreRequest, DatePipeline, PlanResult
from backend.streams.E_orchestrator.models import TimeWindow
from backend.streams.H_conversation.service import default_availability


class ProactiveCheck(BaseModel):
    couple_id: str = Field(min_length=1)
    time_window: TimeWindow | None = None


class OpportunityDecision(BaseModel):
    triggered: bool
    reason: str
    days_since_previous_date: int | None = None
    candidate_count: int
    availability: TimeWindow
    result: PlanResult | None = None


class ProactiveService:
    def __init__(self, pipeline: DatePipeline, minimum_days: int = 14):
        self.pipeline = pipeline
        self.minimum_days = minimum_days

    def check(self, request: ProactiveCheck, now: datetime | None = None) -> OpportunityDecision:
        current = now or datetime.now(timezone.utc)
        window = request.time_window or default_availability(current)
        profile = self.pipeline.memory.get_snapshot(request.couple_id)
        days = None
        if profile.date_history:
            latest = max(item.occurred_at for item in profile.date_history)
            if latest.tzinfo is None:
                latest = latest.replace(tzinfo=timezone.utc)
            days = max(0, (current.date() - latest.date()).days)
        candidates = self.pipeline.discovery.discover(profile, window)
        if days is not None and days < self.minimum_days:
            reason = f"Last date was {days} days ago; threshold is {self.minimum_days} days."
            return OpportunityDecision(triggered=False, reason=reason,
                                       days_since_previous_date=days,
                                       candidate_count=len(candidates), availability=window)
        if not candidates:
            return OpportunityDecision(triggered=False, reason="No matching local activities fit the common availability.",
                                       days_since_previous_date=days,
                                       candidate_count=0, availability=window)
        result = self.pipeline.plan(CoreRequest(couple_id=request.couple_id,
                                                time_window=window, max_plans=1))
        reason = ("No previous date is recorded" if days is None else
                  f"Last date was {days} days ago")
        reason += f"; {len(candidates)} matching activities fit the common availability."
        return OpportunityDecision(triggered=True, reason=reason,
                                   days_since_previous_date=days,
                                   candidate_count=len(candidates), availability=window,
                                   result=result)
