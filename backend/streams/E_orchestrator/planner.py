"""Deterministic filtering, scoring, composition and replacement."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import combinations

from .models import CandidateActivity, CoupleProfile, DatePlan, PlanRequest, PlannedActivity, ReplaceRequest


class NoFeasiblePlan(ValueError):
    pass


@dataclass(frozen=True)
class Rules:
    budget: float
    after: str | None = None
    before: str | None = None
    excluded: tuple[str, ...] = ()
    preferred: tuple[str, ...] = ()


@dataclass(frozen=True)
class Slot:
    activity: CandidateActivity
    start: datetime
    end: datetime
    a_score: float
    b_score: float
    score: float


def parse_constraints(value: str | None, budget: float) -> Rules:
    """Handle a small, documented subset of free text; reject unknown clauses."""
    if not value or not value.strip():
        return Rules(budget=budget)
    text = value.lower().strip()
    clauses = [part.strip() for part in re.split(r"[,;]|\s+and\s+", text) if part.strip()]
    excluded: list[str] = []
    preferred: list[str] = []
    after = before = None
    for clause in clauses:
        if match := re.fullmatch(r"(?:under|below|max(?:imum)?|budget(?: of)?)\s*(?:€|eur\s*)?(\d+(?:\.\d+)?)\s*(?:€|eur)?", clause):
            budget = min(budget, float(match.group(1)))
        elif match := re.fullmatch(r"(?:no|avoid)\s+([\w -]+)", clause):
            excluded.append(match.group(1).strip())
        elif match := re.fullmatch(r"(?:prefer|with)\s+([\w -]+)", clause):
            preferred.append(match.group(1).strip())
        elif match := re.fullmatch(r"after\s+(\d{1,2}:\d{2})", clause):
            after = match.group(1)
        elif match := re.fullmatch(r"before\s+(\d{1,2}:\d{2})", clause):
            before = match.group(1)
        else:
            raise ValueError(f"Unsupported constraint: {clause!r}")
    for name, clock in (("after", after), ("before", before)):
        if clock is not None:
            try:
                datetime.strptime(clock, "%H:%M")
            except ValueError as exc:
                raise ValueError(f"Invalid {name} time: {clock}") from exc
    return Rules(budget, after, before, tuple(excluded), tuple(preferred))


def _clock_on_window(clock: str, request: PlanRequest) -> datetime:
    start = request.time_window.start
    dt = datetime.combine(start.date(), datetime.strptime(clock, "%H:%M").time(), start.tzinfo)
    if request.time_window.end.date() > start.date() and dt < start:
        dt += timedelta(days=1)
    return dt


def _terms(activity: CandidateActivity) -> str:
    return " ".join([activity.type, activity.name, *activity.tags]).lower().replace("_", " ")


def _person_score(activity: CandidateActivity, interests: list[str], dislikes: list[str]) -> float:
    terms = _terms(activity)
    if any(term.lower().replace("_", " ") in terms for term in dislikes):
        return 0.0
    bonus = 0.2 if any(term.lower().replace("_", " ") in terms for term in interests) else 0.0
    return min(1.0, activity.match_score + bonus)


def _score(activity: CandidateActivity, profile: CoupleProfile, preferred: tuple[str, ...]) -> tuple[float, float, float]:
    shared = profile.shared_interests
    a = activity.user_a_score if activity.user_a_score is not None else _person_score(activity, (profile.user_a.interests if profile.user_a else shared), (profile.user_a.dislikes if profile.user_a else []))
    b = activity.user_b_score if activity.user_b_score is not None else _person_score(activity, (profile.user_b.interests if profile.user_b else shared), (profile.user_b.dislikes if profile.user_b else []))
    terms = _terms(activity)
    recent = any(term.lower().replace("_", " ") in terms for term in profile.recent_dates)
    preference = any(term.replace("_", " ") in terms for term in preferred)
    fairness = 0.55 * min(a, b) + 0.45 * (a + b) / 2
    novelty = (0.08 * profile.desired_novelty) * (-1 if recent else 1)
    return a, b, fairness + novelty + (0.08 if preference else 0)


def _distance_minutes(left: Slot, right: Slot) -> float:
    a, b = left.activity.location, right.activity.location
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat, dlng = lat2 - lat1, math.radians(b.lng - a.lng)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    km = 6371 * 2 * math.asin(min(1, math.sqrt(h)))
    return max(5, km / 4.5 * 60 + 5)


def _compatible(left: Slot, right: Slot) -> bool:
    return right.start >= left.end + timedelta(minutes=_distance_minutes(left, right))


def _plan_score(slots: tuple[Slot, ...]) -> float:
    avg = sum(slot.score for slot in slots) / len(slots)
    variety = len({slot.activity.type for slot in slots}) - 1
    gaps = sum((right.start - left.end).total_seconds() / 60 for left, right in zip(slots, slots[1:]))
    return avg + 0.13 * min(variety, 2) + 0.09 * (len(slots) - 1) - 0.0015 * max(0, gaps - 25 * (len(slots) - 1))


def _make_plan(slots: tuple[Slot, ...], index: int, preserved: dict[str, PlannedActivity] | None = None) -> DatePlan:
    activities = []
    for slot in slots:
        item = slot.activity
        if preserved and item.id in preserved:
            activities.append(preserved[item.id])
            continue
        why = f"{item.name} fits this time slot and scores {slot.a_score:.2f} and {slot.b_score:.2f} for the two people."
        activities.append(PlannedActivity(**item.model_dump(include={"id", "type", "name", "start", "end", "price_per_person", "location", "match_score", "booking_url"}), why=why))
    types = ", ".join(item.activity.type for item in slots)
    reason = f"A {len(slots)}-stop date with {types}; it fits the available window, travel time and couple budget. Both people's preferences contribute to the ranking."
    return DatePlan(date_plan_id=f"date_{index:03d}", start=slots[0].start, end=slots[-1].end,
                    estimated_total_eur=round(sum(2 * s.activity.price_per_person for s in slots), 2),
                    reason=reason, activities=activities)


def _prepare(request: PlanRequest) -> tuple[list[Slot], dict[str, str], Rules]:
    profile = request.couple_profile
    rules = parse_constraints(request.constraints, profile.typical_budget if profile.typical_budget is not None else math.inf)
    slots: list[Slot] = []
    rejected: dict[str, str] = {}
    seen: set[str] = set()
    for item in request.candidate_activities or []:
        if item.id in seen:
            raise ValueError(f"Duplicate activity id: {item.id}")
        seen.add(item.id)
        start = _clock_on_window(item.start, request)
        end = _clock_on_window(item.end, request)
        if end <= start:
            end += timedelta(days=1)
        terms = _terms(item)
        why = None
        if start < request.time_window.start or end > request.time_window.end:
            why = "outside available window"
        elif 2 * item.price_per_person > rules.budget:
            why = "over couple budget"
        elif any(term.lower().replace("_", " ") in terms for term in profile.dislikes):
            why = "couple dislike"
        elif any(term.replace("_", " ") in terms for term in rules.excluded):
            why = "excluded by constraint"
        elif rules.after and start < _clock_on_window(rules.after, request):
            why = "before requested start"
        elif rules.before and end > _clock_on_window(rules.before, request):
            why = "after requested end"
        if why:
            rejected[item.id] = why
            continue
        a, b, score = _score(item, profile, rules.preferred)
        slots.append(Slot(item, start, end, a, b, score))
    return sorted(slots, key=lambda slot: (slot.start, slot.activity.id)), rejected, rules


def _fits(slots: tuple[Slot, ...], budget: float) -> bool:
    return (sum(2 * slot.activity.price_per_person for slot in slots) <= budget
            and all(_compatible(left, right) for left, right in zip(slots, slots[1:])))


def _ranked(slots: list[Slot], budget: float, max_plans: int, required: set[str] | None = None,
            replaced: str | None = None, preserved: dict[str, PlannedActivity] | None = None, max_activities: int = 4, must_include: set[str] | None = None) -> list[DatePlan]:
    # Bound the search while retaining the best-scored candidates at each start time.
    fixed = [slot for slot in slots if required and slot.activity.id in required]
    options = fixed + sorted((slot for slot in slots if slot not in fixed), key=lambda s: s.score, reverse=True)[:max(0, 60 - len(fixed))]
    options.sort(key=lambda s: (s.start, s.activity.id))
    choices: list[tuple[float, tuple[Slot, ...]]] = []
    for size in range(1, min(max_activities, len(options)) + 1):
        for combo in combinations(options, size):
            ids = {s.activity.id for s in combo}
            if required is not None and (not required.issubset(ids) or replaced in ids or len(ids) != len(required) + 1):
                continue
            if must_include and not must_include.issubset(ids):
                continue
            if _fits(combo, budget):
                choices.append((_plan_score(combo), combo))
    choices.sort(key=lambda pair: (-pair[0], tuple(s.activity.id for s in pair[1])))
    return [_make_plan(combo, i + 1, preserved) for i, (_, combo) in enumerate(choices[:max_plans])]


def generate(request: PlanRequest, *, max_activities: int = 4, must_include: set[str] | None = None) -> tuple[list[DatePlan], dict[str, str]]:
    slots, rejected, rules = _prepare(request)
    plans = _ranked(slots, rules.budget, request.max_plans, max_activities=max_activities, must_include=must_include)
    if not plans:
        raise NoFeasiblePlan("No feasible date plan for the window, budget and constraints")
    return plans, rejected


def replace(request: ReplaceRequest) -> tuple[list[DatePlan], dict[str, str]]:
    ids = [item.id for item in request.plan.activities]
    if request.replace_activity_id not in ids:
        raise ValueError("replace_activity_id is absent from plan")
    slots, rejected, rules = _prepare(request)
    available = {slot.activity.id: slot for slot in slots}
    kept = set(ids) - {request.replace_activity_id}
    if len(kept) != len(ids) - 1:
        raise ValueError("Plan contains duplicate activity ids")
    for activity in request.plan.activities:
        if activity.id in kept:
            slot = available.get(activity.id)
            expected = slot.activity.model_dump(include={"id", "type", "name", "start", "end", "price_per_person", "location", "match_score", "booking_url"}) if slot else None
            actual = activity.model_dump(exclude={"why"})
            if expected != actual:
                raise ValueError(f"Kept activity unavailable or changed: {activity.id}")
    preserved = {activity.id: activity for activity in request.plan.activities if activity.id in kept}
    plans = _ranked(slots, rules.budget, request.max_plans, kept, request.replace_activity_id, preserved)
    if not plans:
        raise NoFeasiblePlan("No feasible replacement preserves the kept activities")
    return plans, rejected
