"""Boundary for provisional A/B/C inputs and E output."""

from collections.abc import Mapping
from typing import Any

from .models import CandidateActivity, CoupleProfile, DatePlan, TimeWindow


def time_window_from_a(payload: Mapping[str, Any]) -> TimeWindow:
    return TimeWindow.model_validate(payload)


def couple_profile_from_b(payload: Mapping[str, Any]) -> CoupleProfile:
    # The populated shared example uses alternate names. Keep mapping local to E.
    data = dict(payload)
    if "shared_interests" not in data and "likes" in data:
        data["shared_interests"] = data.pop("likes")
    if "typical_budget" not in data and "budget_per_person_max" in data:
        data["typical_budget"] = 2 * data.pop("budget_per_person_max")
    if "desired_novelty" not in data and "novelty_preference" in data:
        data["desired_novelty"] = data.pop("novelty_preference")
    return CoupleProfile.model_validate(data)


def activity_from_c(payload: Mapping[str, Any]) -> CandidateActivity:
    return CandidateActivity.model_validate(payload)


def date_plan_to_contract(plan: DatePlan) -> dict[str, Any]:
    return plan.model_dump(mode="json")
