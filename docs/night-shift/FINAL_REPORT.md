# Chandelle overnight V1 — final handoff

**Result: OVERNIGHT_V1 = PASS** for the offline local backend and FastAPI-served demo.

## Start the demo

From the repository root:

```bash
.venv/bin/python -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/**. Try couple name `demo-couple` and “A cozy jazz date under €80”. Generate a plan, keep or replace an activity, rate it with 😍 / 🙂 / 😐 / 👎, open Memory, then check Proactive suggestion. SQLite data persists under ignored `.runtime/couple_memory.sqlite3`. No frontend build is needed.

## Verified

- Existing E regression remained green. Final full suite: **31 passed in 0.50s** with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider`.
- B persists profile facts, couple interests/dislikes, budget/novelty, date history, selections and feedback in SQLite. A test wrote and read the same database from separate Python processes.
- C consumes B's `CoupleProfile`, filters local Paris listings by availability, weekday, budget, type, tags and dislikes, and emits E candidates. E composes 1–3 plans with travel and total-budget checks.
- H parses a bounded natural-language vocabulary, calls B→C→E, and persists feedback. G explains a date opportunity and calls the same pipeline when triggered.
- FastAPI exposes health, request, replacement, feedback, memory, proactive and run-status routes. An error test verifies 422 plus a failed run record. An end-to-end test denies socket connections while request→feedback→memory→proactive succeeds.
- The page, CSS and JavaScript returned 200 in a manual local `TestClient` smoke. A live request from that smoke returned 200 with one plan. `node --check backend/api/static/app.js` passed. API tests verify replacement preserves other activities and static assets are served. The full suite passed after UI integration.
- Git scope review found no edits by this run to `frontend/`, `backend/shared/`, A/D/F stream directories or `docs/codex-E/`. Pre-existing untracked files outside the allowed scope were left untouched. No commit, remote change or deployment was made.

## Mocked and provisional

- Calendar/common availability is the next Friday 19:00–23:15 Europe/Paris. Activity and provider availability come from packaged Paris fixtures, not live inventory.
- D's normalized Reels/Spotify sample signals are in `mocks/D/signals.json` behind a local adapter and are not automatically imported into B. Booking URLs are preserved; any booking requires human confirmation. No payments or reservations occur.
- H's parser is deterministic and deliberately narrow. OpenAI, Dust and Pipelex are protocol boundaries only; no default code calls them. Gradium/Jinko are outside this V1.
- Models in B/C/API are provisional until shared team contracts are completed. The mapping and endpoint shapes are in `CONTRACTS.md`. Run status is process-local; SQLite couple memory is durable.
- The UI keep control is session-local and blocks replacing that item. Server replacement preserves the other plan activities. Feedback ratings persist to B and update interest/dislike tags from activity types.

## Local smoke limitation

This Codex sandbox rejected a localhost bind on `127.0.0.1:8765` with `operation not permitted`, so a browser/HTTP socket smoke was unavailable here. FastAPI `TestClient` directly verified the same `/`, static asset and request routes. The uvicorn command above is the exact command for a normal local machine with loopback binding.

## Next integration work

Finalize shared schemas; replace the mock calendar, connector and activity repositories with authenticated providers; add consent and real availability checks; connect booking handoff after human confirmation; persist run records and strengthen multi-user concurrency/identity before production use.
