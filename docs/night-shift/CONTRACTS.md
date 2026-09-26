# Provisional Integration Contracts

These contracts are local overnight compatibility contracts, not finalized team-wide contracts.
Do not modify backend/shared to match this file.

## B output — CoupleProfile
Minimum concepts:
- couple_id
- shared_interests
- dislikes
- typical_budget
- desired_novelty
- recent_dates
- preference facts / feedback summary
- updated_at

Implemented as `backend.streams.B_memory.models.CoupleProfile`. `MemoryService.get_snapshot(couple_id)` returns it; unknown ids receive an empty default snapshot. `typical_budget` is the total EUR budget for two. Optional `user_a` and `user_b` carry individual interests/dislikes when known; absent values preserve E's shared-interest fallback. `preference_facts`, `date_history`, `selections`, and `feedback` carry provenance and history. Integration maps `snapshot.model_dump(mode="json")` through E's existing `couple_profile_from_b` adapter.

## C input
- CoupleProfile snapshot from B
- requested time window / constraints
- local activity repository

Implemented as `DiscoveryService.discover(B.CoupleProfile, E.TimeWindow, DiscoveryConstraints)`. `LocalActivityRepository` reads packaged Paris listings; the repository protocol allows a future provider. Optional budget is couple total EUR. Candidate times are local `HH:MM` slots and listings carry weekday availability.

## C output
Candidate activities compatible with E's current local activity model, or mapped through an explicit adapter.

Implemented as `list[E.CandidateActivity]`, ranked by B preferences with profile-aware scores. E retains final full-plan budget, travel and combination checks.

## E input/output
Use the verified E local models and document mapping assumptions.

`backend.api.pipeline.DatePipeline` passes `E.PlanRequest(time_window, couple_profile, candidate_activities, max_plans)` to `E.planner.generate`. B maps through E's existing `couple_profile_from_b`. C outputs E candidates directly. The API adjusts E's total budget to the tighter of persisted B and request-specific cap. E returns 1–3 `DatePlan` objects or raises `NoFeasiblePlan`.

## H request
Minimum:
- couple_id
- text
- optional time window
- optional explicit budget/categories/constraints

Implemented as `H.DateRequest`: `couple_id`, `text`, optional `time_window`, `budget`, `categories`, `required_tags`, `excluded_tags`, `profile_update`, `max_plans`. The deterministic parser recognizes `under/below/budget [€]amount`, tags jazz/cinema/art/museum/wine/comedy/outdoors/food, and `no/avoid tag`. Unknown phrasing does not become an E constraint. Missing window uses the next Friday local mock A slot.

## Integrated response
- run_id
- DatePlan(s)
- concise explanation
- compact trace of B/C/E stages
- mocked/real flags for external intelligence layers

`PlanResult` implements this shape with `external_systems="mocked/local"` and `booking_requires_human_confirmation=true`; run records are process-local for V1.
It also returns `availability` and `budget_cap` for subsequent activity replacement. `POST /v1/date/replace` accepts `ActivityReplacement(couple_id, time_window, plan, replace_activity_id, budget_cap)` and calls E's verified replacement function after reloading B and C. Other activities in the plan remain fixed.

## Feedback
Minimum:
- couple_id
- date_plan_id
- rating / sentiment
- optional activity-level feedback
- optional free text

Implemented as `H.FeedbackRequest`: rating 1–5, sentiment positive/neutral/negative, `liked_tags`, `disliked_tags`, free text, optional selected/rejected decision, and optional occurred-at/activities for date history. The application persists all through B. API routes: `GET /health`, `POST /v1/date/request`, `POST /v1/date/feedback`, `GET /v1/couples/{couple_id}/memory`, `GET /v1/runs/{run_id}`.

## G proactive
`ProactiveCheck` accepts `couple_id` and optional `time_window`; absent window uses mock A availability. `OpportunityDecision` includes `triggered`, explanation, date recency, candidate count, availability and optional integrated `PlanResult`. Endpoint: `POST /v1/proactive/check`.

## Offline external boundaries
Mock A availability is `H.default_availability`. C's Paris fixture stands in for real place/event providers. `mocks/D/signals.json` contains normalized sample Spotify/Reels signals through `LocalConnectorSignals`, currently outside the automatic planning path. `LocalBookingHandoff` preserves a booking URL and requires human confirmation; E preserves activity URLs in plans. Protocols for Dust, Pipelex and OpenAI are in `backend/api/external.py`; H's `ConstraintParser` protocol is the active language boundary. No default path makes external calls.

## Demo UI
FastAPI serves `/`, `/static/styles.css`, and `/static/app.js`. The browser calls the documented API routes; it has no frontend build or external asset request. The keep control is session-local and prevents a pinned item being the replacement target. Feedback and learned memory persist in B.
