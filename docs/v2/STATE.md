# V2 build state

STATUS: COMPLETE
V2_DONE = PASS
LAST_UPDATED: 2026-09-26

## Baseline
Executed `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider`: 31 passed in 0.50s before changes. Existing V1 tests remain unchanged and pass in the final 104-test suite.

## Delivered gates
0. Baseline, architecture/contract/data/UX docs and independent architecture review.
1. SQLite scoped memory, consent, provenance, conflict/correction, fusion retrieval, profiles, export/erasure and resumable dual onboarding.
2. Persistent 40-entry fictional catalog, hard filters, separate person context, fairness, evidence and activity feedback.
3. Real opt-in OpenAI SDK Responses adapter, Pydantic outputs, ID rejection, safe fallback, local semantics and optional embedding call.
4. V2 wrapper around E, 1–3 maximum stops, selected-ID enforcement, timeline/travel/cost, keep/replace/status, history/reviews/photos and memory loop.
5. Persistent proactive feed using same B→C→E pipeline; explainable triggers, dedup/cooldown/actions and provider interfaces.
6. Authenticated V2 API, error envelopes, durable runs, idempotent interview/review/actions, developer commands and migration/init.
7. Mobile-first no-build SPA, dual private interviews, Home/Ask/Discover/Memories/History, detail and settings; all product actions call real APIs.
8. Full regression, isolation, API lifecycle, fake OpenAI, upload security, reopen/migration, frontend/static and no-network checks passed. Final handoff in FINAL_REPORT.md.

## Final evidence
104 passed in 5.84s using the global network-denial runner. Node syntax/privacy module checks and actual frontend-shaped TestClient flow passed. See TEST_MATRIX.md for all commands, intermediate failures and repairs.

## Run
`scripts/run_v2_demo.sh` → http://127.0.0.1:8000/ (alias /app). Original V1 UI /v1/demo. OpenAI disabled by default. Explicit CHANDELLE_DEV=1 reveals developer seed/reset.

## Scope and limitations
No commits, remotes, pushes, deployments or live API requests. No shared/A/D/F or original night-shift files edited. Pre-existing AGENTS.md/.gitignore changes, README-SETUP.md, night-shift/AGENTS-V1.md and MASTER_PROMPT.txt retained.
Local device capabilities are not production authentication. Catalog/calendar are mock/internal. Live providers and real-browser visual QA remain future validation; all requested offline flows are verified through tests/TestClient.
