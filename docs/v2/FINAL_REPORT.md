# Chandelle V2 final report

V2_DONE = PASS

The verified V1 has been preserved and extended into a local-first V2 with durable dual onboarding, separate personal memories, consent-derived Couple profiles, a persistent activity catalog, fair recommendations, date history/reviews/photos, proactive suggestions and a connected mobile-first application.

## Run offline

```bash
.venv/bin/python scripts/init_v2_demo.py
scripts/run_v2_demo.sh
```

Open **http://127.0.0.1:8000/** (alias `/app`). Original V1 UI: `/v1/demo`. API docs: `/docs`. No npm build, external assets, API key or cloud service is needed. Dependency versions are pinned in `backend/requirements-v2.txt` for recreating the existing environment.

For the explicit developer shortcut, start `CHANDELLE_DEV=1 scripts/run_v2_demo.sh`, then Settings → Developer demo seed. Normal first launch requires both interviews. Reset instructions and the full walkthrough are in [DEMO_SCRIPT.md](DEMO_SCRIPT.md).

## Architecture delivered

- Root-owned versioned SQLite schema, managed connections, separate default V2 database and backward-compatible initialization. Existing V1 couple memory stays intact.
- B native scoped repository/service: PERSON, COUPLE, SESSION and DATE; normalized facts, append-only provenance, idempotency, explicit supersession/conflicts, FTS5 where available, local semantic signals, entity links, retrieval fusion, reinforcement/decay, profiles, sharing/revocation, export and erasure. Optional Mem0-compatible protocol boundary; no copied or required Mem0 package.
- Onboarding service: two independent seven-step interviews, privacy per answer, skip/resume, member capability checks, raw answer storage and B ingestion. Couple derivation and application unlock occur only after both complete. Same-answer retry, answer reversal and later corrections have regression coverage.
- C: 40 persistent fictional internal activities with metadata, search/filter/state and separate A/B/Couple context. Hard constraints precede scoring. C uses `.60 × min(A,B) + .40 × mean(A,B)` with documented novelty, distance and diversity adjustments. Public explanations show catalog evidence, not private memory prose.
- E: existing deterministic travel/time/budget/replacement behavior preserved; backward-compatible optional maximum stops and required IDs support V2. V2 wrapper supplies unique persisted plan IDs, scores, timelines, status, cost, source/mode metadata, reviews and owner-only local photos. E's existing internal combination scoring remains unchanged for V1 compatibility.
- G: persistent feed, opportunity scores/reasons, common mock slot, date recency, saved activities and consented recent changes; same B→C→E pipeline, deduplication, dismissal cooldown, snooze, acceptance and regeneration. Catalog ranking incorporates recent completed dates and novelty. Calendar/weather/catalog provider interfaces are optional boundaries.
- API: protected V2 resources, consistent errors, server onboarding gate, durable traces, developer controls, memory/conversation ingestion and local uploads. Original V1 routes remain available and isolated from V2 personal data.
- Frontend: local HTML/CSS/ES modules; warm responsive layout, keyboard focus, error/loading/empty states, real API requests and private handoffs. Uninstalled Next starter is preserved.

## Working screens

Welcome/couple creation; Person A interview; neutral handoff; Person B interview; shared initial summary; Home; Ask with filters/trace; Discover and activity detail; Person/Couple Memories with edit/share/revoke/provenance; History; plan detail/timeline/keep/replace/status; reviews and photos; Settings/integration metadata/developer controls; edit-own-onboarding.

## Privacy and data model

Person facts belong to their authenticated owner; partner personal retrieval is denied, including onboarding, provenance, DATE review facts, exports and photos. Shared-device tokens are random capabilities hashed in SQL and returned once at creation. Local storage keeps both for explicit device handoff. Anyone controlling the local device can switch identities; this is deliberately not production authentication.

PRIVATE is excluded from planning. COUPLE_RECOMMENDATION permits structured internal influence without exposing raw prose. SHARED allows shared visibility. Public Couple profiles use explicitly shared facts and safe common-category/numeric aggregates; private/recommendation free text is absent. Private identity answers never replace public welcome pseudonyms. Revoke/delete rebuild profiles and remove searchable indexes as appropriate.

Reviews update only the submitting person's preferences under chosen consent. Completed history creates DATE memories. Dynamic owner-filtered reviews/photos and private planning snapshots are excluded from persisted public plan payloads. Private facts do not affect proactive change counts. Ordinary deletion keeps audit provenance; memory-scope erasure removes scoped facts/events/indexes. Full personal erasure additionally removes raw answers, messages, reviews, photos and activity state, re-locking onboarding while preserving the partner and shared plan records.

Uploads accept local PNG/JPEG only, ≤5 MB, with extension/MIME/signature checks, generated UUID filenames, owner authorization, nosniff and deletion. Files live under ignored `.runtime/uploads/`; original names never determine paths. There is no execution or external upload.

## OpenAI: real adapter, mocked verification

Installed SDK 3.19.2 was inspected and the adapter was checked against [official Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs). It uses Responses `parse` with Pydantic schemas, `store=False`, a 12-second timeout and one bounded SDK retry. Request parsing, candidate memory extraction, conflict classification, explanation and optional reranking are implemented. Unknown/duplicate candidate IDs, malformed output and provider failures use deterministic fallback. Explanation payloads contain only public catalog fields/numeric scores; individual extraction receives only the current person's submitted text. No prompts, keys or provider exception bodies are logged.

Configuration: `OPENAI_ENABLED`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL`. A key alone never enables calls; Ask also requires selecting OpenAI. Default model names are configurable defaults, not guarantees of account availability. Local deterministic embeddings remain the automatic memory path; remote embedding calls are explicit and optional.

No live request was made. The separate `RUN_LIVE_OPENAI_SMOKE=1 .venv/bin/python scripts/live_openai_smoke.py` additionally requires enabled/configured credentials and is excluded from tests. Full offline operation remains available on failure.

## Exact validation evidence

Baseline before edits:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
31 passed in 0.50s
```

Final full suite (all socket connections forbidden):

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/test_v2_offline.py
104 passed in 5.84s
```

Breakdown: 31 original V1 tests + 19 B memory tests + 5 C discovery tests + 21 fake OpenAI tests + 23 API lifecycle/security tests + 5 final migration/system tests. All original 31 tests remain unmodified and are included. Additional coverage includes B isolation/conflicts/ranking/reopen, C fairness/hard constraints, 21 fake OpenAI cases, API lifecycle/security, uploads, migration/fresh process, required catalog activity, typed errors and personal erasure.

Also executed successfully:

```text
node --check frontend/v2/app.mjs
node frontend/v2/test_ui.mjs
.venv/bin/python frontend/v2/verify_api.py
bash -n scripts/run_v2_demo.sh scripts/reset_v2_demo.sh
.venv/bin/python scripts/init_v2_demo.py --database /tmp/chandelle-v2-init-check.sqlite3
git diff --check
```

Frontend checks cover first-run lock, one-completed lock, resume, token isolation, clearing the previous private screen, settings gate and private identity labels. Actual TestClient payloads exercise 14 interview answers, two completions, nine screen endpoints, query/selected activity/accept/review/memory edit. API tests cover photo upload/deletion, history/reopen and changed proactive recommendations. Browserless checks are verified; a graphical browser session and live provider calls were not performed.

`TEST_MATRIX.md` records intermediate failures and repairs, including a SQL quoting error and a network-runner import guard issue. Neither failed invocation was counted as a final pass.

## Migration and scope

V2 creates prefixed tables and schema version 1; it does not reinterpret or migrate legacy couple_profiles into personal facts because V1 lacks individual consent. Existing V1 users can continue at `/v1/demo`; V2 begins with explicit dual onboarding. Default V1 and V2 database paths differ. Schema initialization and reopen preserve legacy records, including across a fresh Python process.

Only authorized implementation paths were changed. Shared models, A/D/F streams and original V1 documentation were not edited. Existing local AGENTS.md/.gitignore modifications and untracked setup/prompt files predated this work and were preserved. No commit, remote change, push, deployment, purchase or live API request occurred. `.runtime`, uploads and `.env` are ignored; tracked secret/runtime filename inspection returned no matches.

## Limits and next integrations

- Catalog entries and availability are fictional/internal; calendar is the existing next-Friday mock. No reservations, payments, maps or live weather occur. Booking links require explicit human action; demo fixtures have no real booking targets.
- This is a local single-device product. Production identity, cross-device sessions, database encryption, multi-worker transaction stress and migration from external user accounts need separate work.
- The deterministic language fallback recognizes a bounded vocabulary; arbitrary prose is retained privately and OpenAI extraction can be enabled. Optional Mem0, remote embeddings, weather, real calendar and live activity providers are boundaries, not verified external services.
- Upload validation is bounded local file validation; there is no image re-encoding, metadata stripping or antivirus pipeline. Photos default owner-only.
- Layout and interactions have browserless/static/API verification, not screenshot or graphical-browser visual certification.

Next provider work: authenticated calendar availability, real venue/catalog availability with source freshness, weather hooks, stronger local identity, production-safe media processing and explicit booking handoff. These are outside the verified offline demonstration.

## Exact implementation files

- `backend/api/app.py`
- `backend/api/v2.py`
- `backend/db/__init__.py`
- `backend/db/database.py`
- `backend/domain/onboarding.py`
- `backend/domain/planning.py`
- `backend/integrations/openai/__init__.py`
- `backend/requirements-v2.txt`
- `backend/streams/B_memory/test_v2_memory.py`
- `backend/streams/B_memory/v2.py`
- `backend/streams/C_discovery/test_v2_discovery.py`
- `backend/streams/C_discovery/v2.py`
- `backend/streams/E_orchestrator/planner.py`
- `backend/streams/G_proactive/providers.py`
- `backend/streams/G_proactive/v2.py`
- `backend/tests/test_v2_api.py`
- `backend/tests/test_v2_openai.py`
- `backend/tests/test_v2_system.py`
- `docs/v2/ARCHITECTURE.md`
- `docs/v2/CONTRACTS.md`
- `docs/v2/DATA_MODEL.md`
- `docs/v2/DECISIONS.md`
- `docs/v2/DEMO_SCRIPT.md`
- `docs/v2/FINAL_REPORT.md`
- `docs/v2/HANDOFFS.md`
- `docs/v2/STATE.md`
- `docs/v2/TEST_MATRIX.md`
- `docs/v2/UX_SPEC.md`
- `docs/v2/reviews/architecture-review.md`
- `docs/v2/reviews/qa-review.md`
- `frontend/v2/app.mjs`
- `frontend/v2/index.html`
- `frontend/v2/style.css`
- `frontend/v2/test_ui.mjs`
- `frontend/v2/verify_api.py`
- `scripts/init_v2_demo.py`
- `scripts/live_openai_smoke.py`
- `scripts/reset_v2_demo.sh`
- `scripts/run_v2_demo.sh`
- `scripts/test_v2_offline.py`
