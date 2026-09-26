# Night Shift Handoffs

## Gate 0 — audit
E local `PlanRequest` accepts `TimeWindow`, `CoupleProfile`, and explicit `CandidateActivity` list; `planner.generate` returns plans and rejected candidates. Existing E suite: 13 passed. FastAPI, Pydantic v2, pytest are installed. `backend/shared` stays read-only.

## Gate 1 — B → downstream
`MemoryService(SQLiteMemoryRepository(path))` exposes `get_snapshot(couple_id)`, `update_profile(couple_id, ProfileUpdate)`, `record_selection(couple_id, SelectionRecord)`, `record_date(couple_id, DateHistoryEntry)`, and `ingest_feedback(couple_id, FeedbackRecord)`. `get_snapshot` returns B `CoupleProfile`; serialize with `model_dump(mode="json")` to feed E's `couple_profile_from_b`. Budget is total EUR for two. Additional persisted facts, feedback, selection and history remain on B snapshot. SQLite default is `.runtime/couple_memory.sqlite3`; tests use temporary paths. Four B tests passed, including reopen.

## Gate 2 — C → E
`DiscoveryService(LocalActivityRepository()).discover(b_profile, e_time_window, DiscoveryConstraints(...))` returns ranked `list[E.CandidateActivity]`. `DiscoveryConstraints` supports `include_types`, `required_tags`, `excluded_tags`, `max_total_budget` (EUR for two), and `limit`. C filters on weekday, time, individual affordability, types, tags and B dislikes; it scores with B interests and novelty. API must also pass any explicit budget cap to E so the full plan total is capped. C tests and combined B/C/E tests passed (20 total).

## Gate 3 — integrated core pipeline
`DatePipeline(memory, discovery).plan(CoreRequest(...))` loads/updates B, sends B snapshot to C, then adapts B and passes explicit C candidates to E. Returns `PlanResult` with 1–3 plans, B/C/E trace, run ID and human booking confirmation flag. The API applies the explicit discovery budget to E's full-plan budget. One integration test passed.

## Gate 4 — H feedback loop
`ConversationService.request_date(DateRequest)` uses `MockConstraintParser` for budget/tag language and calls the same `DatePipeline`. Explicit `time_window`, budget, categories and tags override or extend parsed terms. Missing time uses mock A availability (next Friday 19:00–23:15 Paris). `submit_feedback(FeedbackRequest)` records optional selection/date history plus feedback through B; repository reopen retains it. FastAPI exposes health, request, feedback, memory and run status. Four focused H/API tests passed.

## Gate 5 — G proactive
`ProactiveService(pipeline).check(ProactiveCheck(couple_id, optional time_window))` uses B date history, C candidates and mock A availability. Default threshold is 14 days. `OpportunityDecision` includes trigger, reason, days since previous date, candidate count and availability. Triggered decisions include a `PlanResult` from the same B→C→E pipeline. `POST /v1/proactive/check` exposes it. Six G/API focused tests passed.

## Gate 6 — system QA
Full backend suite: 30 passed. API system test denies socket connections while request→feedback→memory→proactive succeeds. A separate Python writer and reader process prove SQLite persistence. Git scope review showed this run changed only allowed backend stream/API/docs areas; pre-existing untracked root/docs files remain untouched.

## Gate 7 — clickable demo
`GET /` serves `backend/api/static/index.html`; `/static/styles.css` and `/static/app.js` serve without a build. UI calls actual local endpoints for date request, activity replacement, feedback, memory and proactive checks. The keep control protects an activity from replacement in the current UI session; E replacement preserves all other activities. Manual in-process static smoke returned 200 for HTML/CSS/JS and a live request. Final 31-test suite passed. Sandbox denied a real localhost bind; run the documented uvicorn command on a machine that allows loopback binding.
