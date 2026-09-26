"""Deterministic local filtering and couple-aware candidate scoring."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from backend.streams.B_memory.models import CoupleProfile
from backend.streams.E_orchestrator.models import CandidateActivity, TimeWindow

from .models import ActivityListing, DiscoveryConstraints
from .repository import ActivityRepository


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", value.casefold())).strip()


def _contains(terms: str, needle: str) -> bool:
    token = _normalize(needle)
    return bool(token and re.search(r"(?<!\w)" + re.escape(token) + r"(?!\w)", terms))


def _terms(candidate: CandidateActivity) -> str:
    return _normalize(" ".join([candidate.name, candidate.type, *candidate.tags]))


def _slot(listing: ActivityListing, window: TimeWindow) -> tuple[datetime, datetime]:
    candidate = listing.candidate
    start = datetime.combine(window.start.date(), datetime.strptime(candidate.start, "%H:%M").time(),
                             window.start.tzinfo)
    if window.end.date() > window.start.date() and start < window.start:
        start += timedelta(days=1)
    end = datetime.combine(start.date(), datetime.strptime(candidate.end, "%H:%M").time(),
                           window.start.tzinfo)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def _score(candidate: CandidateActivity, profile: CoupleProfile) -> CandidateActivity:
    terms = _terms(candidate)
    shared = any(_contains(terms, tag) for tag in profile.shared_interests)
    recent = any(_contains(terms, name) for name in profile.recent_dates)

    def person_score(person) -> float:
        individual = person is not None and any(_contains(terms, tag) for tag in person.interests)
        return min(1.0, candidate.match_score + (0.12 if shared else 0) +
                   (0.18 if individual else 0))

    a = person_score(profile.user_a)
    b = person_score(profile.user_b)
    novelty_penalty = 0.16 * profile.desired_novelty if recent else 0
    rank = max(0.0, min(1.0, 0.55 * min(a, b) + 0.45 * (a + b) / 2 - novelty_penalty))
    return candidate.model_copy(update={"match_score": round(rank, 4),
                                        "user_a_score": round(a, 4),
                                        "user_b_score": round(b, 4)})


class DiscoveryService:
    def __init__(self, repository: ActivityRepository):
        self.repository = repository

    def discover(self, profile: CoupleProfile, time_window: TimeWindow,
                 constraints: DiscoveryConstraints | None = None) -> list[CandidateActivity]:
        rules = constraints or DiscoveryConstraints()
        budget_limits = [value for value in (profile.typical_budget, rules.max_total_budget)
                         if value is not None]
        budget = min(budget_limits) if budget_limits else None
        allowed_types = {_normalize(value) for value in rules.include_types}
        required_tags = {_normalize(value) for value in rules.required_tags}
        excluded_tags = {_normalize(value) for value in rules.excluded_tags}
        dislikes = [*profile.dislikes,
                    *(profile.user_a.dislikes if profile.user_a else []),
                    *(profile.user_b.dislikes if profile.user_b else [])]
        results: list[CandidateActivity] = []
        for listing in self.repository.list_activities():
            item = listing.candidate
            start, end = _slot(listing, time_window)
            tags = {_normalize(tag) for tag in item.tags}
            terms = _terms(item)
            if (start < time_window.start or end > time_window.end or
                    start.weekday() not in listing.weekdays or
                    (budget is not None and 2 * item.price_per_person > budget) or
                    (allowed_types and _normalize(item.type) not in allowed_types) or
                    not required_tags.issubset(tags) or bool(excluded_tags & tags) or
                    any(_contains(terms, term) for term in dislikes)):
                continue
            results.append(_score(item, profile))
        results.sort(key=lambda item: (-item.match_score, item.id))
        return results[:rules.limit]
