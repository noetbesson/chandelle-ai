"""Provisional, persistent memory contract for the offline backend."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PersonPreferences(BaseModel):
    interests: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)


class PreferenceFact(BaseModel):
    person: Literal["user_a", "user_b"]
    kind: Literal["interest", "dislike"]
    value: str = Field(min_length=1)
    source: str = "explicit"
    observed_at: datetime = Field(default_factory=utc_now)


class DateHistoryEntry(BaseModel):
    date_plan_id: str = Field(min_length=1)
    occurred_at: datetime
    activities: list[str] = Field(default_factory=list)
    source: str = "date_plan"
    recorded_at: datetime = Field(default_factory=utc_now)


class SelectionRecord(BaseModel):
    date_plan_id: str = Field(min_length=1)
    decision: Literal["selected", "rejected"]
    source: str = "explicit"
    recorded_at: datetime = Field(default_factory=utc_now)


class FeedbackRecord(BaseModel):
    date_plan_id: str = Field(min_length=1)
    rating: int | None = Field(default=None, ge=1, le=5)
    sentiment: Literal["positive", "neutral", "negative"] | None = None
    liked_tags: list[str] = Field(default_factory=list)
    disliked_tags: list[str] = Field(default_factory=list)
    text: str | None = None
    source: str = "post_date"
    recorded_at: datetime = Field(default_factory=utc_now)


class CoupleProfile(BaseModel):
    couple_id: str = Field(min_length=1)
    user_a: PersonPreferences | None = None
    user_b: PersonPreferences | None = None
    shared_interests: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)
    typical_budget: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    desired_novelty: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    recent_dates: list[str] = Field(default_factory=list)
    preference_facts: list[PreferenceFact] = Field(default_factory=list)
    date_history: list[DateHistoryEntry] = Field(default_factory=list)
    selections: list[SelectionRecord] = Field(default_factory=list)
    feedback: list[FeedbackRecord] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class ProfileUpdate(BaseModel):
    user_a: PersonPreferences | None = None
    user_b: PersonPreferences | None = None
    shared_interests: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)
    typical_budget: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    desired_novelty: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    source: str = "explicit"
    observed_at: datetime = Field(default_factory=utc_now)

    @field_validator("shared_interests", "dislikes")
    @classmethod
    def nonempty_terms(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("preference terms must not be blank")
        return values
