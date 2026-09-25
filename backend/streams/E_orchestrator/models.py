"""Provisional E-local models. Replace through adapters when shared schemas exist."""

from __future__ import annotations

from datetime import datetime, time
import re
from typing import Annotated

from pydantic import BaseModel, Field, model_validator


Score = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Money = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class TimeWindow(BaseModel):
    start: datetime
    end: datetime
    duration_minutes: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_window(self):
        if (self.start.tzinfo is None) != (self.end.tzinfo is None):
            raise ValueError("window start and end must use the same timezone convention")
        actual = (self.end - self.start).total_seconds() / 60
        if actual <= 0:
            raise ValueError("window end must follow start")
        if self.duration_minutes is not None and abs(actual - self.duration_minutes) > 0.001:
            raise ValueError("duration_minutes must equal end minus start")
        return self


class PersonPreferences(BaseModel):
    interests: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)


class CoupleProfile(BaseModel):
    shared_interests: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)
    typical_budget: Money | None = None  # Total for two people.
    desired_novelty: Score = 0.5
    recent_dates: list[str] = Field(default_factory=list)
    user_a: PersonPreferences | None = None
    user_b: PersonPreferences | None = None


class Location(BaseModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)


class CandidateActivity(BaseModel):
    id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    start: str
    end: str
    price_per_person: Money
    location: Location
    match_score: Score = 0.5
    booking_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    user_a_score: Score | None = None
    user_b_score: Score | None = None

    @model_validator(mode="after")
    def validate_times(self):
        for value in (self.start, self.end):
            if not re.fullmatch(r"\d{2}:\d{2}", value):
                raise ValueError("activity start/end must be local HH:MM times")
            try:
                time.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("activity start/end must be local HH:MM times") from exc
        return self


class PlannedActivity(BaseModel):
    id: str
    type: str
    name: str
    start: str
    end: str
    price_per_person: Money
    location: Location
    match_score: Score
    why: str
    booking_url: str | None = None


class DatePlan(BaseModel):
    date_plan_id: str
    start: datetime
    end: datetime
    estimated_total_eur: Money
    reason: str
    activities: list[PlannedActivity] = Field(min_length=1)


class PlanRequest(BaseModel):
    time_window: TimeWindow
    couple_profile: CoupleProfile
    candidate_activities: list[CandidateActivity] | None = None
    constraints: str | None = None
    max_plans: int = Field(default=3, ge=1, le=3)


class ReplaceRequest(PlanRequest):
    plan: DatePlan
    replace_activity_id: str


class PlansResponse(BaseModel):
    run_id: str
    status: str
    plans: list[DatePlan]
    rejected: dict[str, str] = Field(default_factory=dict)
