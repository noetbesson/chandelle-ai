# Test evidence

## Gate 0
Executed `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider`: **31 passed in 0.50s**.
Future required gates: B isolation/reopen/conflicts/retrieval/privacy; onboarding idempotency/resume/consent; C fairness/constraints; fake OpenAI and network guard; plans/reviews/uploads; G persistent actions; API errors/static/browserless end-to-end; complete regression.

## Implemented component checks
- `.venv/bin/python -m pytest -q backend/streams/B_memory/test_memory.py backend/streams/B_memory/test_v2_memory.py`: 20 passed in 0.35s (agent execution).
- `.venv/bin/python -m pytest backend/streams/C_discovery/test_v2_discovery.py backend/streams/C_discovery/test_discovery.py -q`: 9 passed (agent execution).
- `.venv/bin/python -m pytest backend/tests/test_v2_openai.py -q`: 21 passed (agent execution).
- `node --check frontend/v2/app.mjs` and `node frontend/v2/test_ui.mjs`: passed (agent execution; privacy handoff/resume module tests).
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider`: 73 passed in 1.17s before API end-to-end tests were added.
- Root temporary-database TestClient developer seed → query → accept → review → suggestion smoke: all returned HTTP 200. No socket used.

## Integration and final QA
- `.venv/bin/python -m pytest backend/tests/test_v2_api.py -q`: 23 passed in 3.95s (QA agent); all socket connects denied.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider`: 103 passed in 5.54s (root, before final DATE-history and UI fixes).
- `.venv/bin/python frontend/v2/verify_api.py`: passed actual static/onboarding/nine-screen/query/selected-activity/accept/review/memory-edit payload sequence.
- `.venv/bin/python scripts/init_v2_demo.py --database /tmp/chandelle-v2-init-check.sqlite3`: passed, initialized schema/catalog.

### Failures encountered and repaired
- Full-suite collection briefly failed with 3 collection errors due to SQL string quoting in G privacy filter. Corrected quoting; next full suite passed 96 tests.
- First global network-guard script executed pytest on import, recursively collecting itself: inner 103 tests passed but wrapper exited 3 with SystemExit collection error. Added main guard; only a subsequent clean exit is accepted as evidence.

## Final acceptance evidence
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/test_v2_offline.py`: **103 passed in 5.68s**, exit 0. Globally forbids socket.connect, connect_ex and create_connection; no live provider tests run.
- `node --check frontend/v2/app.mjs`: exit 0.
- `node frontend/v2/test_ui.mjs`: PASS: welcome/partial-completion gate, private handoff, server resume, active-token isolation, old-screen removal, pre-onboarding settings gate, private identity labels.
- `.venv/bin/python frontend/v2/verify_api.py`: PASS: static assets, 14 interview answers, 2 completions, 9 screen endpoints, query, selected activity inclusion, accept, category review, memory edit.
- `bash -n scripts/run_v2_demo.sh scripts/reset_v2_demo.sh`: exit 0.
- `git diff --check`: exit 0.
- `git check-ignore .runtime/chandelle_v2.sqlite3 .runtime/uploads/example.png .env`: all three ignored.
- Protected-path diff check (`backend/shared`, A/D/F streams, `docs/codex-E`, `docs/night-shift`): no tracked modifications. Pre-existing untracked night-shift AGENTS copy retained.
- Tracked secret/runtime filename check `git ls-files '.env*' '.runtime/*' '*.sqlite*' '*secret*'`: empty.
- Final full suite after adding full personal-data erasure: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/test_v2_offline.py` → **104 passed in 5.84s**, exit 0. This is the final acceptance count (31 original + 73 new). Earlier standard full invocation before this final addition: 103 passed in 5.64s.
