# Night Shift Decisions

Append-only. Do not rewrite prior decisions without recording a superseding decision.

## D-001 — Preserve shared contracts
The existing shared JSON files are incomplete/empty. Overnight work will not modify them. Integration models remain provisional and local.

## D-002 — Persistent local product memory
Use a repository abstraction with SQLite under .runtime/ for the default B implementation. Tests use temporary databases.

## D-003 — Offline-first overnight build
Default tests and demo fixtures use no external paid APIs. Real service integrations are adapter boundaries only.

## D-004 — E is a verified dependency
Treat existing Stream E as a stable component and modify it only for demonstrated integration defects.

## D-005 — B snapshot as provisional integration source
Use B's Pydantic `CoupleProfile` as the downstream source of truth. The API converts it at the E boundary using E's existing adapter. Budget values are total EUR for two; B persists full snapshots as JSON in SQLite to keep the local repository small and deterministic.

## D-006 — Discovery hands E validated candidates
C consumes B's snapshot directly and returns E's `CandidateActivity` model. The local repository owns provider normalization and weekday fixtures. E remains responsible for full-plan combination, travel and total-budget validation.

## D-007 — Local H parser and mock A window
The default conversation path uses deterministic phrase extraction and a next-Friday Paris availability slot. Parser and availability are replaceable boundaries; default tests do not invoke OpenAI or Google Calendar. Failed pipeline runs retain process-local error status by run ID.

## D-008 — Proactive threshold
G triggers when no previous date is recorded or at least 14 days have passed and C finds candidates within mock common availability. It calls the same integrated pipeline for a one-plan recommendation, keeping decisions deterministic and explainable.

## D-009 — FastAPI-served standalone demo
Serve plain HTML/CSS/JavaScript from `backend/api/static` so the clickable demo requires no frontend build or new dependency. The UI calls the real local API. Activity keep state is local to the current browser session; replacement is validated and composed by B→C→E on the server. Feedback is durable in B.
