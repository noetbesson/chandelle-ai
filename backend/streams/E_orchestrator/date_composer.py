"""Pure, bounded composition over already filtered activities; no network or storage."""
from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations
from math import ceil

from .models import DatePlan, PlanRequest
from .planner import Slot, _distance_minutes, _fits, _make_plan, _prepare

# All components are normalized to 0..1. Hard constraints run BEFORE this score.
SCORE_WEIGHTS = {"taste_match": .35, "availability": .20, "distance_fit": .15,
                 "budget_fit": .10, "novelty": .10, "popularity": .10}
DIVERSITY_STRENGTH = .65
MAX_CANDIDATES = 100  # at most 161,700 triples, never an unbounded cartesian product


def weighted_score(components: dict[str, float]) -> float:
    if set(components) != set(SCORE_WEIGHTS):
        raise ValueError("Missing score component")
    if any(not 0 <= value <= 1 for value in components.values()):
        raise ValueError("Score components must be finite numbers in 0..1")
    return round(sum(components[key] * weight for key, weight in SCORE_WEIGHTS.items()), 6)


def score_candidates(rows: list[dict], budget: float, distance_scale_km: float = 10) -> list[dict]:
    """Uses B/C consent-filtered scores. Unknown popularity is neutral, never a rating."""
    scored = []
    for row in rows:
        activity, current = row['activity'], row['components']
        price = activity['price_per_person'] * 2
        popularity = activity.get('popularity')
        components = {
            'taste_match': min(1, current['fairness'] + current.get('shared_bonus', 0) + current.get('query_bonus', 0)),
            'availability': 1.0,  # within the supplied published/demo window, NOT a booking guarantee
            'distance_fit': max(0, 1 - current['distance_km'] / max(1, distance_scale_km)),
            'budget_fit': max(0, 1 - price / budget) if budget else float(price == 0),
            'novelty': 0.0 if current.get('novelty_penalty', 0) else 1.0,
            'popularity': float(popularity) if isinstance(popularity, (int, float)) and 0 <= popularity <= 1 else .5,
        }
        score = weighted_score(components)
        scored.append({**row, 'candidate': {**row['candidate'], 'match_score': score},
                       'couple_score': score, 'scoring_components': components})
    return scored


@dataclass(frozen=True)
class DatePlanCandidate:
    slots: tuple[Slot, ...]
    score: float
    budget: float
    categories: frozenset[str]
    moods: frozenset[str]

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(slot.activity.id for slot in self.slots)


def generate_candidate_combos(
    scored_activities: list[Slot], requested_steps: int,
    max_total_duration_minutes: int, max_travel_time_minutes: int = 30, *,
    budget: float = float('inf'), required_ids: set[str] | None = None,
    required_categories: set[str] | None = None,
    category_order: list[str] | None = None,
) -> list[DatePlanCandidate]:
    """Enumerate exact-size feasible combinations, with a five-minute walking margin."""
    if not 1 <= requested_steps <= 3 or not 1 <= max_total_duration_minutes <= 1440:
        raise ValueError('Invalid step count or duration')
    if not 0 <= max_travel_time_minutes <= 180 or len(scored_activities) > MAX_CANDIDATES:
        raise ValueError('Invalid travel limit or too many candidates')
    ordered = sorted(scored_activities, key=lambda s: (s.start, s.activity.id))
    if len({s.activity.id for s in ordered}) != len(ordered):
        raise ValueError('Duplicate candidate ID')
    result = []
    for slots in combinations(ordered, requested_steps):
        ids = {s.activity.id for s in slots}
        cats = frozenset(s.activity.type for s in slots)
        if required_ids and not required_ids <= ids:
            continue
        if required_categories and not required_categories <= cats:
            continue
        if category_order:
            positions=[next((i for i,s in enumerate(slots) if s.activity.type==cat),-1) for cat in category_order]
            if -1 in positions or positions!=sorted(positions):continue
        duration = (slots[-1].end - slots[0].start).total_seconds() / 60
        if duration > max_total_duration_minutes or not _fits(slots, budget):
            continue
        if any(ceil(_distance_minutes(a, b)) > max_travel_time_minutes for a, b in zip(slots, slots[1:])):
            continue
        # Equal step weights; reward complementary categories, penalize long idle gaps.
        idle = sum(max(0, (b.start-a.end).total_seconds()/60 - _distance_minutes(a,b)) for a,b in zip(slots,slots[1:]))
        score = sum(s.score for s in slots)/len(slots) + .06*(len(cats)-1) - .001*max(0,idle-45)
        moods = frozenset(t for s in slots for t in s.activity.tags if t in {'quiet','romantic','creative','loud','nature','music','cozy'})
        result.append(DatePlanCandidate(slots, score, round(sum(s.activity.price_per_person*2 for s in slots),2), cats, moods))
    return sorted(result, key=lambda c: (-c.score, c.ids))


def similarity(left: DatePlanCandidate, right: DatePlanCandidate) -> float:
    def jaccard(a, b):
        return len(a & b)/len(a | b) if a or b else 0
    overlap = jaccard(set(left.ids), set(right.ids))
    category = jaccard(left.categories, right.categories)
    same_budget = abs(left.budget-right.budget) <= .15*max(left.budget,right.budget,1)
    return .50*overlap + .25*category + .15*same_budget + .10*jaccard(left.moods,right.moods)


def select_diverse_top_3(candidates: list[DatePlanCandidate], strength: float = DIVERSITY_STRENGTH) -> list[DatePlanCandidate]:
    """Greedy maximal marginal relevance; never duplicate a plan to fake three results."""
    if not 0 <= strength <= 1:
        raise ValueError('Invalid diversification strength')
    remaining = sorted({c.ids:c for c in candidates}.values(), key=lambda c: (-c.score,c.ids))
    selected: list[DatePlanCandidate] = []
    while remaining and len(selected) < 3:
        best = max(remaining, key=lambda c: c.score*(1-strength*max((similarity(c,p) for p in selected),default=0)))
        selected.append(best)
        remaining.remove(best)
    return selected


def candidate_plans(request: PlanRequest, steps: int, duration: int, travel: int,
                    required_ids: set[str] | None = None, required_categories: set[str] | None = None,
                    fixed_selection: bool = False, category_order: list[str] | None = None) -> tuple[list[DatePlan], dict]:
    slots, rejected, rules = _prepare(request)
    # _prepare revalidates hard exclusions; the score already comes from the six C components.
    slots = [replace(s, score=s.activity.match_score) for s in slots]
    if fixed_selection:
        # Validate ONE fixed selection in linear time, even beyond three activities.
        ordered=tuple(sorted(slots,key=lambda s:(s.start,s.activity.id)))
        valid=(1<=steps<=50 and len(ordered)==steps and {s.activity.id for s in ordered}==set(required_ids or ())
               and (ordered[-1].end-ordered[0].start).total_seconds()/60<=duration and _fits(ordered,rules.budget)
               and all(ceil(_distance_minutes(a,b))<=travel for a,b in zip(ordered,ordered[1:])))
        plans=[_make_plan(ordered,1)] if valid else []
        return plans,{'candidate_count':len(slots),'combos_generated':int(valid),'selected_activity_ids':[[s.activity.id for s in ordered]] if valid else []}
    combos = generate_candidate_combos(slots, steps, duration, travel, budget=rules.budget,
                                       required_ids=required_ids, required_categories=required_categories,category_order=category_order)
    chosen = combos[:1] if fixed_selection else select_diverse_top_3(combos)
    plans = [_make_plan(c.slots, index+1) for index,c in enumerate(chosen)]
    return plans, {'candidate_count':len(slots), 'combos_generated':len(combos),
                   'selected_activity_ids':[list(c.ids) for c in chosen], 'rejected_count':len(rejected),
                   'scoring_backend':'local_deterministic', 'diversity_strength':DIVERSITY_STRENGTH}


def describe_plan(plan: DatePlan) -> tuple[str, str]:
    names = {'food':'dîner','culture':'culture','concerts':'concert','cinema':'cinéma','outdoors':'balade',
             'sport':'sport','workshops':'atelier','nightlife':'bar','home':'à la maison','travel':'escapade'}
    label = ' puis '.join(names.get(a.type,a.type) for a in plan.activities).capitalize()
    minutes = round((plan.end-plan.start).total_seconds()/60)
    reason = (f"{len(plan.activities)} étape{'s' if len(plan.activities)>1 else ''} sur {minutes} minutes, "
              f"pour {plan.estimated_total_eur:g} € à deux. Les trajets à pied estimés sont compatibles avec les horaires. "
              "Le classement tient compte des préférences autorisées des deux profils.")
    return label, reason
