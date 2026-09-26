"""Deterministic memory updates; extraction can be added outside this service."""

from __future__ import annotations

from .models import (
    CoupleProfile,
    DateHistoryEntry,
    FeedbackRecord,
    PersonPreferences,
    PreferenceFact,
    ProfileUpdate,
    SelectionRecord,
    utc_now,
)
from .repository import MemoryRepository


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
