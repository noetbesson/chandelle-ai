"""Compatibilité V1 uniquement ; le produit actuel utilise service.py."""


from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from pathlib import Path
import sqlite3
from typing import Protocol


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






DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / ".runtime" / "couple_memory.sqlite3"


class MemoryRepository(Protocol):
    def get(self, couple_id: str) -> CoupleProfile | None: ...

    def save(self, profile: CoupleProfile) -> CoupleProfile: ...


class SQLiteMemoryRepository:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS couple_profiles "
                "(couple_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def get(self, couple_id: str) -> CoupleProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM couple_profiles WHERE couple_id = ?", (couple_id,)
            ).fetchone()
        return CoupleProfile.model_validate_json(row[0]) if row else None

    def save(self, profile: CoupleProfile) -> CoupleProfile:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO couple_profiles (couple_id, payload) VALUES (?, ?) "
                "ON CONFLICT(couple_id) DO UPDATE SET payload = excluded.payload",
                (profile.couple_id, profile.model_dump_json()),
            )
        return profile





def _merge_terms(existing: list[str], incoming: list[str]) -> list[str]:
    by_key = {item.strip().casefold(): item.strip() for item in existing if item.strip()}
    for item in incoming:
        clean = item.strip()
        if clean:
            by_key.setdefault(clean.casefold(), clean)
    return [by_key[key] for key in sorted(by_key)]


def _without_terms(values: list[str], excluded: list[str]) -> list[str]:
    blocked = {value.casefold() for value in excluded}
    return [value for value in values if value.casefold() not in blocked]


class MemoryService:
    def __init__(self, repository: MemoryRepository):
        self.repository = repository

    def get_snapshot(self, couple_id: str) -> CoupleProfile:
        if not couple_id.strip():
            raise ValueError("couple_id must not be blank")
        return self.repository.get(couple_id) or CoupleProfile(couple_id=couple_id)

    def update_profile(self, couple_id: str, update: ProfileUpdate) -> CoupleProfile:
        profile = self.get_snapshot(couple_id).model_copy(deep=True)
        for person_key in ("user_a", "user_b"):
            incoming: PersonPreferences | None = getattr(update, person_key)
            if incoming is None:
                continue
            current: PersonPreferences = getattr(profile, person_key) or PersonPreferences()
            current.interests = _merge_terms(current.interests, incoming.interests)
            current.dislikes = _merge_terms(current.dislikes, incoming.dislikes)
            current.interests = _without_terms(current.interests, current.dislikes)
            setattr(profile, person_key, current)
            for kind, values in (("interest", incoming.interests), ("dislike", incoming.dislikes)):
                for value in values:
                    if value.strip():
                        profile.preference_facts.append(
                            PreferenceFact(person=person_key, kind=kind, value=value.strip(),
                                           source=update.source, observed_at=update.observed_at)
                        )
        profile.shared_interests = _merge_terms(profile.shared_interests, update.shared_interests)
        profile.dislikes = _merge_terms(profile.dislikes, update.dislikes)
        profile.shared_interests = _without_terms(profile.shared_interests, profile.dislikes)
        if update.typical_budget is not None:
            profile.typical_budget = update.typical_budget
        if update.desired_novelty is not None:
            profile.desired_novelty = update.desired_novelty
        profile.updated_at = utc_now()
        return self.repository.save(profile)

    def record_selection(self, couple_id: str, selection: SelectionRecord) -> CoupleProfile:
        profile = self.get_snapshot(couple_id).model_copy(deep=True)
        profile.selections = [entry for entry in profile.selections
                              if entry.date_plan_id != selection.date_plan_id]
        profile.selections.append(selection)
        profile.updated_at = utc_now()
        return self.repository.save(profile)

    def record_date(self, couple_id: str, entry: DateHistoryEntry) -> CoupleProfile:
        profile = self.get_snapshot(couple_id).model_copy(deep=True)
        profile.date_history = [item for item in profile.date_history
                                if item.date_plan_id != entry.date_plan_id]
        profile.date_history.append(entry)
        profile.date_history.sort(key=lambda item: (item.occurred_at.isoformat(), item.date_plan_id))
        profile.recent_dates = _merge_terms([], [name for date in profile.date_history[-10:]
                                                  for name in date.activities])
        profile.updated_at = utc_now()
        return self.repository.save(profile)

    def ingest_feedback(self, couple_id: str, feedback: FeedbackRecord) -> CoupleProfile:
        profile = self.get_snapshot(couple_id).model_copy(deep=True)
        profile.feedback.append(feedback)
        profile.shared_interests = _merge_terms(profile.shared_interests, feedback.liked_tags)
        profile.dislikes = _merge_terms(profile.dislikes, feedback.disliked_tags)
        profile.shared_interests = _without_terms(profile.shared_interests, profile.dislikes)
        profile.updated_at = utc_now()
        return self.repository.save(profile)
