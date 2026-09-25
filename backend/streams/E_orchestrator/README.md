# Stream E — Date Orchestrator

Stream E accepts an available window, a couple profile, candidate activities, and optional text constraints. It returns 1–3 ranked date plans or an infeasibility error. Planning and explanations are deterministic; no LLM, network connection, booking, or paid API is required.

## Provisional contracts

`models.py` defines **E-local compatibility models** based on the examples supplied for A, B, C, and DatePlan on 2026-09-25. They are **not finalized team-wide contracts**. The shared `activity.json` and `date-plan.json` files and A/B/C/E stream JSON files are empty. `adapters.py` is the replacement boundary when those contracts are finalized. It also maps the populated shared B example's `likes`, `budget_per_person_max`, and `novelty_preference` fields into the provisional profile. E accepts either both offset-aware datetimes or both local datetimes. E does not modify shared files.

The example's `typical_budget` is treated as a **total couple budget** in euros. `price_per_person` is multiplied by two. The populated shared B example's `budget_per_person_max` is doubled in the adapter. If no budget is supplied, no budget ceiling is imposed. Activity times are local `HH:MM` and are resolved against the window date. An overnight window supports activities after midnight. The optional `user_a_score` and `user_b_score` allow per-person scoring from upstream; otherwise each person's interests/dislikes and the candidate match score are used. Shared interests apply to both people. The plan's `match_score` remains the candidate's source score; the ranking uses a separate fairness score.

## Behavior

- Rejects activities outside the window, over budget individually, matching couple dislikes or exclusions, or violating requested start/end limits.
- Builds schedules with no overlap and enough walking time between locations (4.5 km/h plus five minutes). Limits plans to four activities.
- Ranks with the weaker person's score weighted more heavily, then adds type variety, multi-stop coherence, preferred terms, and novelty while penalizing long gaps/recent repeats.
- Replacement requires each kept activity to appear unchanged in the candidate set. It chooses one different activity and preserves the kept activity objects, including their explanations. It recalculates budget, timing, and travel feasibility.
- Searches the 60 highest-scored candidates for each request, always retaining kept activities during replacement. This is a bounded local search, not a proof of globally optimal ranking for larger sets.
- Text constraints support comma/semicolon/`and` separated clauses: `under €90`, `max 90`, `no comedy`, `avoid formal restaurants`, `prefer jazz`, `with music`, `after 20:00`, `before 23:00`. Unsupported clauses return HTTP 422 instead of being silently ignored.

## API and local data

From the repository root:

```bash
.venv/bin/uvicorn backend.streams.E_orchestrator.api:app --reload
```

`POST /plans` takes a `PlanRequest` with `time_window`, `couple_profile`, optional `candidate_activities`, optional `constraints`, and `max_plans` (1–3). If candidates are omitted, it loads `mocks/E/activities.json`. An explicit empty list means no candidates and returns HTTP 422. `POST /plans/replace` takes the same fields plus `plan` and `replace_activity_id`. Successful responses contain `run_id`, `status`, `plans`, and per-activity `rejected` reasons. Failure responses include a `run_id` in the error detail. `GET /runs/{run_id}` reports `running`, `completed`, or `failed`, with timestamps and plan count/error. `GET /health` reports process health. Runs are supervised **in memory**; status disappears on process restart and is local to one worker.

Example request:

```json
{
  "time_window": {"start": "2026-09-25T19:30", "end": "2026-09-25T23:45", "duration_minutes": 255},
  "couple_profile": {"shared_interests": ["jazz", "japanese_food"], "dislikes": ["formal_restaurants"], "typical_budget": 110, "desired_novelty": 0.75, "recent_dates": ["cinema"]},
  "constraints": "after 20:00",
  "max_plans": 3
}
```

## Tests

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider backend/streams/E_orchestrator/test_orchestrator.py
```

The tests exercise validation, dates, filtering, budgets, travel/overlap, fairness, replacement, adapters, and local FastAPI run status. They use the local repository and do not call an external service.
