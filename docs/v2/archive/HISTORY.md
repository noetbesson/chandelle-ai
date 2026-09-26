# Historique de construction — référence uniquement

Les textes ci-dessous sont conservés pour provenance. Leurs chemins, commandes et consignes sont historiques ; voir ../ARCHITECTURE.md pour le projet actuel.


---

## Source : docs/v2/archive/FINAL_REPORT.md

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


---

## Source : docs/v2/archive/HANDOFFS.md

# Ownership and handoffs

Root owns database, architecture/contracts, domain/API/integrations, G/H integration and final QA. Architecture reviewer owns only reviews/architecture-review.md. B and C assigned disjoint modules/tests after contracts. Frontend assigned frontend/v2 after API contracts. No shared file concurrent edits.

B delivered scoped memory + 16 tests. C delivered 40-entry catalog + 5 tests. Frontend delivered SPA and browserless privacy tests. QA delivered 21 OpenAI fake tests and read-only review, now running API end-to-end coverage. Root integration verified first full offline loop. Root owns all subsequent cross-file fixes.

## Final handoff
All agent tasks integrated; final root no-network regression: 103 passed in 5.68s. Final frontend privacy fixes prevent private identity changing public labels and prevent Settings revealing main nav during onboarding. Root added DATE completion memory, tighter replacement budget, selected activity constraints, script main guard and protected-path checks. No pending integration blocker. See FINAL_REPORT.md and DEMO_SCRIPT.md.
Final addition: authenticated personal-data erasure now removes raw interview answers and all owned data while preserving partner records and re-locking onboarding. Final global network-denial suite increased to **104 passed in 5.84s**. Final report and state updated to this count.


---

## Source : docs/v2/archive/MASTER_PROMPT.txt

/goal Transform the verified Chandelle overnight V1 into a substantially more complete, polished and testable Chandelle V2 application.

Read first:
- AGENTS.md
- docs/night-shift/FINAL_REPORT.md
- docs/night-shift/STATE.md
- docs/night-shift/CONTRACTS.md
- backend/streams/B_memory/
- backend/streams/C_discovery/
- backend/streams/E_orchestrator/
- backend/streams/G_proactive/
- backend/streams/H_conversation/
- backend/api/
- frontend/

Do not throw away working behavior. Begin by running the existing complete test suite and recording the baseline.

==================================================
PRODUCT VISION
==================================================

Chandelle is a personal agent for a couple. It must understand two distinct people, learn from their behavior, find or retrieve relevant activities, recommend fair compromises, proactively suggest dates, compose coherent plans, and learn after each date.

Build a real local-first product V2 with:
- a required first-run dual onboarding in which Person A and Person B each complete a separate 2–3 minute interview to seed their own memory;
- separate memory for Person A;
- separate memory for Person B;
- a derived/shared Couple memory;
- a richer internal activity catalog;
- an OpenAI-powered recommendation and memory-extraction path with a deterministic offline fallback;
- proactive suggestion feeds;
- history, reviews and local photos;
- a significantly richer, navigable, mobile-first frontend;
- persistent storage, traceability and tests.

The end-to-end experience must be demonstrable locally without cloud services, while the real OpenAI integration is ready to enable through environment variables.

==================================================
FIRST-RUN DUAL ONBOARDING — REQUIRED
==================================================

Before the normal application navigation is shown for a new couple, create a short onboarding flow that seeds Person A memory, Person B memory and the first derived Couple profile.

This onboarding is mandatory for a newly created couple, but a clearly labeled demo-seed shortcut may exist in the developer panel.

The onboarding must be quick:
- target completion time: 2–3 minutes per person;
- 7 core questions maximum per person, plus optional details;
- use chips, sliders, short selections and at most one optional free-text answer;
- show progress and allow resume after interruption;
- every non-essential question can be skipped.

Required flow:

1. Welcome
   - explain that Chandelle learns each person separately;
   - explain that private answers are not shown to the other person;
   - create a local couple with two member profiles;
   - collect first name or pseudonym for Person A and Person B;
   - optional avatar/initials only; no production authentication is required for the local V2.

2. Person A interview
   - complete in a private screen;
   - do not display Person B answers;
   - at completion, show a neutral handoff screen such as "Pass the device to Person B";
   - hide Person A answers before Person B starts.

3. Person B interview
   - same questions and privacy controls;
   - do not reveal Person A answers.

4. Couple profile derivation
   - only derive Couple memory from facts explicitly allowed for couple recommendations;
   - never copy private free text into Couple memory;
   - show a concise, non-sensitive summary such as shared interests, compatible budget range and desired novelty;
   - allow each person to edit their own answers later from Memories or Settings.

Core interview questions for each person:

1. Identity
   - first name or pseudonym;
   - optional pronouns.

2. Activities and interests
   - select favorite categories such as food, culture, concerts, cinema, outdoors, sport, workshops, nightlife, home dates and travel;
   - optional "something else" text.

3. Hard dislikes and no-goes
   - categories, environments or activities to avoid;
   - food, sensory, accessibility or safety constraints may be added here.

4. Typical date budget
   - per person or couple;
   - support a range and "flexible".

5. Preferred date energy/style
   - calm ↔ energetic;
   - intimate ↔ social;
   - familiar ↔ surprising;
   - indoor ↔ outdoor;
   - short ↔ full evening.

6. Practical preferences
   - preferred days/times;
   - maximum travel time/radius;
   - accessibility and dietary constraints.

7. Experience seed
   - one optional date/activity they loved;
   - one optional date/activity they would avoid repeating.

Privacy and consent:

For onboarding answers, support at least:
- PRIVATE: available only to that person-scoped memory and never shown to the partner;
- COUPLE_RECOMMENDATION: may influence couple recommendations but must not be shown verbatim to the partner;
- SHARED: may appear in the Couple profile and be visible to both people.

Provide a simple default visibility for ordinary taste answers, but make the meaning visible and allow per-answer override.
Free-text answers should default to PRIVATE or COUPLE_RECOMMENDATION, not SHARED.

Data and state:

Persist:
- couple onboarding status;
- Person A status: not_started / in_progress / completed;
- Person B status: not_started / in_progress / completed;
- current interview step for resume;
- raw answer event with provenance;
- normalized memory facts created from answers;
- privacy/consent selection;
- completion timestamps;
- derived Couple profile version.

Each answer must create or update the correct PERSON-scoped memory through the same memory ingestion system used elsewhere.
Couple memory must be derived only after applying consent rules.
The onboarding must never write Person A answers into Person B memory or vice versa.

Application behavior:

- on first launch with no completed couple, route to onboarding before Home;
- if only one person has completed, show the handoff/resume screen rather than the main dashboard;
- when both are complete, build the initial Couple profile and enter Home;
- preserve a developer-only reset and demo-seed option;
- onboarding completion must be idempotent and safe to retry.

Required tests:

- Person A and Person B answers persist separately;
- Person A private answers never appear in Person B retrieval or UI payloads;
- Person B private answers never appear in Person A retrieval or UI payloads;
- Couple profile uses only allowed shared/derived facts;
- interrupted onboarding resumes at the correct step;
- completing the same step twice is idempotent;
- both-completed status unlocks the main application;
- one-completed status does not expose that person's private answers to the other;
- editing an onboarding answer later updates the proper profile snapshot and provenance.

==================================================
DURABLE BUILD MEMORY
==================================================

Create and maintain:
- docs/v2/STATE.md
- docs/v2/DECISIONS.md
- docs/v2/ARCHITECTURE.md
- docs/v2/CONTRACTS.md
- docs/v2/UX_SPEC.md
- docs/v2/DATA_MODEL.md
- docs/v2/HANDOFFS.md
- docs/v2/TEST_MATRIX.md
- docs/v2/FINAL_REPORT.md

Before every gate, reread STATE.md, DECISIONS.md, CONTRACTS.md and TEST_MATRIX.md.
After every gate, update STATE.md, HANDOFFS.md and TEST_MATRIX.md.

==================================================
SUBAGENT PLAN
==================================================

If native Codex subagents are available, use them for independent work with strict file ownership:

1. Architecture reviewer
   - read-only audit;
   - proposes contracts, migration risks and integration map;
   - writes only docs/v2/reviews/architecture-review.md.

2. Memory engineer
   - owns backend/streams/B_memory/ and its focused tests;
   - implements the entity-scoped memory system below.

3. Recommendation engineer
   - owns backend/streams/C_discovery/ and focused recommendation tests;
   - may propose E changes but must not edit E concurrently with the root agent.

4. Frontend engineer
   - owns frontend/;
   - consumes API contracts written by root agent;
   - must not invent frontend-only data.

5. QA/security reviewer
   - read-only review plus tests under backend/tests/ where non-overlapping;
   - focuses on memory isolation, API errors, uploads and regression.

The root agent owns database schema/migrations, backend/api/, backend/domain/, backend/integrations/, G/H integration, any E changes, and final system integration.

If subagents are unavailable, execute the same plan sequentially. Never block on their absence.

==================================================
GATE 0 — BASELINE, CHECKPOINT AND ARCHITECTURE
==================================================

1. Run the current full test suite.
2. Inspect the current application and final report.
3. Inventory all existing endpoints, models, repositories and static UI assets.
4. Record the exact baseline in docs/v2/STATE.md.
5. Design a backward-compatible V2 architecture.
6. Do not start the rewrite until ARCHITECTURE.md, DATA_MODEL.md, CONTRACTS.md and UX_SPEC.md are coherent.

Preserve current V1 endpoints where practical; add V2 endpoints rather than breaking the demo.

==================================================
GATE 1 — MEM0-INSPIRED MULTI-ENTITY MEMORY
==================================================

Build a production-shaped local memory layer inspired by these concepts:
- first-run onboarding ingestion and resumable completion state for both people;
- entity-scoped memories;
- extracted durable facts rather than replaying whole transcripts;
- append-only provenance;
- deduplication;
- entity linking;
- keyword + semantic + entity + temporal retrieval signals;
- profile snapshots;
- reinforcement/decay;
- feedback and explicit correction;
- strict isolation between users.

Do not copy Mem0 code. Implement an internal interface and a native backend.

Required scopes:
- PERSON memory for Person A;
- PERSON memory for Person B;
- COUPLE memory for shared/derived knowledge;
- SESSION memory for temporary conversation state;
- DATE memory for plans, outcomes, reviews and feedback.

Privacy/consent rules:
- a private Person A memory must never appear in Person B memory retrieval;
- a private Person B memory must never appear in Person A memory retrieval;
- Couple memory may contain only explicitly shared facts or transparent derived aggregates;
- every fact must carry privacy_scope and consent_state;
- UI/API must allow edit, delete, share-to-couple and revoke-sharing;
- tests must prove there is no cross-person leak.

Create a repository abstraction and a SQLite implementation with migrations/schema versioning.

Persist at minimum:
- users;
- couples;
- couple memberships and roles;
- append-only memory events;
- normalized memory facts;
- source/provenance;
- categories and tags;
- entities and links;
- confidence;
- salience;
- privacy scope;
- consent state;
- valid_from / valid_to;
- created_at / updated_at;
- last_accessed_at;
- reinforcement_count;
- supersedes / contradicted_by;
- derived profile snapshots;
- conversations and messages;
- date history;
- activity feedback;
- saved/rejected activities.

Use SQLite FTS5 for local keyword retrieval when available.
Create a semantic retrieval interface:
- optional OpenAI embeddings implementation;
- deterministic/local fallback when embeddings are unavailable.
Store embedding metadata separately so the source of truth remains SQL facts/metadata.

Implement retrieval fusion using transparent weighted signals:
- lexical relevance;
- optional semantic similarity;
- entity overlap;
- recency/temporal relevance;
- confidence;
- salience;
- reinforcement/soft decay.

Never silently overwrite a conflicting fact.
New facts should either:
- coexist with temporal validity;
- supersede an older fact explicitly;
- be marked contradictory and queued for resolution.

Create profile views:
- Person A profile;
- Person B profile;
- Couple profile;
- current top preferences;
- dislikes/hard constraints;
- budget;
- novelty appetite;
- recent patterns;
- unresolved conflicts;
- provenance summary.

Implement:
- create local couple and two member profiles;
- create/resume/complete Person A and Person B onboarding interviews;
- ingest onboarding answers into the correct PERSON scope with consent metadata;
- derive the first Couple profile only from allowed facts;
- report onboarding status without exposing either person's private answers;
- manual memory CRUD;
- ingest conversation;
- ingest onboarding;
- ingest date history;
- ingest likes/dislikes/saves;
- ingest feedback/review;
- retrieve relevant memories for a query;
- rebuild profile snapshot;
- export one entity's memories;
- delete one entity's data.

Add an optional Mem0-compatible backend adapter/protocol, but do not require mem0ai to run the app.

Gate acceptance:
- a newly created couple cannot enter the main application until both interviews are complete, except through a clearly labeled developer demo seed;
- onboarding can be interrupted and resumed;
- onboarding answers seed Person A and Person B memory separately;
- Couple profile derivation obeys privacy/consent;
- persistence across repository/process reopen;
- strict entity isolation tests;
- conflict/supersession tests;
- retrieval ranking tests;
- profile generation tests;
- edit/delete/share/revoke tests.

==================================================
GATE 2 — INTERNAL ACTIVITY CATALOG AND DISCOVERY
==================================================

Expand C into a real internal catalog and discovery service.

Create a persistent activity schema with:
- stable id;
- title;
- description;
- category/subcategory;
- tags;
- price and currency;
- typical duration;
- location/address/lat/lng;
- neighborhood;
- indoor/outdoor;
- weather sensitivity;
- accessibility metadata;
- opening/time windows;
- availability source and last_verified_at;
- booking URL;
- image/media references;
- popularity/rating fields;
- provider/source/provenance;
- demo/live status;
- hard constraints;
- embedding metadata if available.

Seed a rich internal demo catalog sufficient to exercise the interface.
Clearly label demo/internal data. Never imply fictitious fixtures are live or verified venues.

Build:
- catalog browse/search/filter;
- saved/rejected state per person;
- candidate retrieval based on query + memories;
- hard filters for time, budget, dislikes, accessibility and availability;
- geographic/travel compatibility;
- novelty and history penalties;
- diversity across categories;
- transparent scoring.

Couple fairness:
- calculate Person A score;
- calculate Person B score;
- calculate a fair couple score that strongly penalizes one-sided recommendations;
- expose scoring components and reasons;
- exclusions are hard filters, not compensated by average score.

A reasonable starting formula is:
0.60 × min(person_a_score, person_b_score)
+ 0.40 × mean(person_a_score, person_b_score)
then apply constraint, novelty, distance, timing and diversity adjustments.
Document and test the final formula.

The LLM must never invent activity facts.
It may only select, order or explain activities whose IDs were retrieved from the catalog/provider layer.

Gate acceptance:
- C genuinely retrieves Person A, Person B and Couple context separately;
- no cross-person memory leak;
- filters/ranking tested;
- candidate explanations include evidence;
- offline deterministic mode works.

==================================================
GATE 3 — REAL OPENAI INTEGRATION WITH SAFE FALLBACK
==================================================

Create backend/integrations/openai/ using the current OpenAI Python SDK and Responses API.

Use environment configuration:
- OPENAI_API_KEY
- OPENAI_MODEL
- OPENAI_EMBEDDING_MODEL
- OPENAI_ENABLED
- RUN_LIVE_OPENAI_SMOKE

No key may be stored in the repository.

Implement structured/Pydantic outputs for:
1. natural-language request parsing;
2. candidate memory-fact extraction;
3. memory conflict classification;
4. personalized plan explanation;
5. optional recommendation reranking over already-retrieved candidate IDs.

Rules:
- deterministic calculations remain outside the LLM;
- pass only relevant scoped memories, not the whole database;
- never send Person A private memories when processing Person B;
- couple planning receives only allowed Person A, Person B and Couple context;
- include candidate IDs in structured output;
- reject unknown/hallucinated candidate IDs;
- validate every response;
- use timeouts, bounded retries and clear fallback behavior;
- redact secrets and avoid logging private prompt content;
- default tests use a fake OpenAI client;
- live smoke is a separate script and must not run unless RUN_LIVE_OPENAI_SMOKE=1.

Offline behavior:
- deterministic parser;
- deterministic memory extraction for known demo patterns;
- deterministic ranking/explanation fallback;
- application remains fully usable without an API key.

Add an integration-status endpoint that reports configured/disabled without exposing credentials.

Gate acceptance:
- mocked structured-output tests;
- malformed response tests;
- timeout/fallback tests;
- hallucinated candidate ID rejection test;
- private-memory scoping test;
- no default test opens a socket.

==================================================
GATE 4 — RICH DATE PLANNING, HISTORY AND REVIEWS
==================================================

Enhance E and the surrounding domain without breaking its verified behavior.

DatePlan must support:
- 1–3 activities;
- timeline and travel segments;
- total couple cost;
- per-person cost;
- reason and evidence;
- Person A match score;
- Person B match score;
- couple score;
- keep/replace controls;
- plan status: draft, proposed, accepted, completed, cancelled;
- booking actions that require human confirmation;
- source/verification badges;
- generated_at and model/mode metadata.

History:
- persist accepted/completed/cancelled plans;
- date detail page data;
- overall rating;
- per-activity ratings;
- free-text review;
- what to repeat/avoid;
- local photos;
- review visibility/private/shared;
- post-date memory ingestion.

Photo handling:
- local development upload only;
- store files under ignored .runtime/uploads/;
- validate size, extension and MIME type;
- generate safe filenames;
- never execute uploaded content;
- persist metadata in SQLite;
- provide deletion.

Replacement:
- preserve explicitly kept activities;
- explain why replacement is compatible;
- keep budget/time/travel coherence.

Gate acceptance:
- history persistence;
- review-to-memory loop;
- upload validation/security tests;
- replacement regression tests;
- V1 E tests remain green.

==================================================
GATE 5 — PROACTIVE SUGGESTION ENGINE
==================================================

Turn G into a persistent proactive suggestion system.

Signals:
- next common free slot from current mock/adapter;
- days since last completed date;
- saved activities;
- recent memory changes;
- new catalog candidates;
- budget cadence;
- novelty appetite;
- anniversaries/occasions if known;
- dismissed/snoozed suggestions;
- weather/provider hooks as interfaces only.

Persist suggestion objects with:
- suggestion_id;
- couple_id;
- opportunity score;
- trigger reasons;
- generated DatePlan;
- state: new, viewed, accepted, dismissed, snoozed, expired;
- created_at/expires_at;
- evidence and source;
- mode: offline/openai.

Build:
- create/check suggestion;
- list feed;
- accept;
- dismiss;
- snooze;
- regenerate;
- learn from outcomes.

A suggestion must call the same B → C → E pipeline, not a parallel shortcut.

Gate acceptance:
- explainable score;
- persistent feed;
- deduplication/cooldown;
- accept/dismiss/snooze tests;
- feedback affects future suggestions.

==================================================
GATE 6 — VERSIONED FASTAPI APPLICATION
==================================================

Create a coherent versioned API while preserving practical V1 compatibility.

Suggested V2 surfaces:
- /api/v2/health
- /api/v2/integrations
- /api/v2/onboarding/status
- /api/v2/onboarding/couples
- /api/v2/onboarding/couples/{couple_id}/members/{member_id}
- /api/v2/onboarding/couples/{couple_id}/members/{member_id}/answers
- /api/v2/onboarding/couples/{couple_id}/members/{member_id}/complete
- /api/v2/users
- /api/v2/couples
- /api/v2/couples/{couple_id}/profile
- /api/v2/memories
- /api/v2/memories/search
- /api/v2/memories/{memory_id}
- /api/v2/memories/{memory_id}/share
- /api/v2/activities
- /api/v2/recommendations/query
- /api/v2/date-plans
- /api/v2/date-plans/{id}
- /api/v2/date-plans/{id}/replace
- /api/v2/date-plans/{id}/feedback
- /api/v2/suggestions
- /api/v2/suggestions/check
- /api/v2/history
- /api/v2/history/{id}
- /api/v2/uploads
- /api/v2/runs/{run_id}

Exact routes may differ if CONTRACTS.md explains them.

Requirements:
- Pydantic validation;
- consistent error envelope;
- pagination/filtering where relevant;
- idempotency for feedback/suggestion actions where practical;
- run tracing;
- no secrets in responses;
- migration/init command;
- demo seed command;
- OpenAPI remains usable.

Gate acceptance:
- focused API tests;
- onboarding create/status/resume/complete API tests;
- API payloads never reveal one person's private onboarding answers to the other person;
- invalid input tests;
- not-found/conflict tests;
- private memory authorization/scope tests;
- end-to-end request → plan → accept → review → memory → new suggestion.

==================================================
GATE 7 — COMPLEX MOBILE-FIRST FRONTEND
==================================================

Build a polished, navigable, clickable frontend.

Use the simplest robust approach supported by the existing environment:
- if an existing frontend framework/build setup is already operational, extend it;
- otherwise create a no-build modular SPA with HTML/CSS/ES modules served locally by FastAPI;
- do not make React/npm installation a blocker;
- no external CDN is required for the demo.

Create a coherent design system:
- warm, intimate Chandelle identity;
- mobile-first;
- responsive desktop view;
- accessible contrast and focus states;
- loading, empty, success and error states;
- skeletons/progress for agent runs;
- no dead buttons.

FIRST-RUN ONBOARDING UI

Before Main navigation, build:
- Welcome screen explaining separate memories and privacy;
- local couple creation with Person A and Person B names/pseudonyms;
- a private 7-question interview for Person A;
- a neutral "Pass the device to Person B" privacy handoff screen;
- a private 7-question interview for Person B;
- progress indicator and resume support;
- privacy/visibility choice for answers;
- a final shared summary that contains no private verbatim answers;
- automatic transition to Home only after both interviews are completed;
- a developer-only demo seed/reset path;
- edit-later links to the proper Person memory screen.

The onboarding must use real backend onboarding endpoints and persist across refresh/restart.
Do not keep onboarding state only in JavaScript.
Do not show either person's raw private answers during the other person's interview.

Main navigation:
1. Home
2. Ask
3. Discover
4. Memories
5. History

HOME
- couple identity and greeting;
- next free slot;
- proactive suggestion cards;
- saved plans;
- recent memory insight;
- quick actions;
- accept/dismiss/snooze proactive suggestions.

ASK
- natural-language query;
- explicit filters: date, time, budget, categories, radius, number of activities;
- switch between Offline and OpenAI when configured;
- visible stage progress: parse → memories → candidates → plan;
- trace/evidence drawer;
- 1–3 plan cards;
- plan timeline;
- keep/replace;
- accept plan.

DISCOVER
- browse/search internal catalog;
- category chips and filters;
- activity detail;
- Person A score, Person B score and Couple score;
- reasons/evidence;
- save/like/dislike per person;
- add to plan.

MEMORIES
- tabs: Person A, Person B, Couple;
- derived profile header;
- searchable/filterable memories;
- category, source, confidence, salience, recency and privacy badges;
- provenance view;
- add/edit/delete;
- share to couple;
- revoke sharing;
- unresolved conflicts;
- clear warning when a memory is private.

HISTORY
- date timeline/list;
- detail page;
- photos;
- overall and per-activity reviews;
- tags learned from feedback;
- repeat/avoid actions;
- empty state and seeded demo data.

PLAN DETAIL
- timeline;
- map/location summary without requiring a map provider;
- cost;
- travel;
- explanations;
- source/live-demo badges;
- replace one activity;
- confirm/complete/cancel;
- booking links only after explicit user action.

SETTINGS/DEV PANEL
- demo seed/reset controls;
- integration status;
- OpenAI enabled/disabled;
- model names without keys;
- database/schema version;
- link to API docs.

All screens must call real local API endpoints.
Do not use frontend-only fabricated results.
Preserve useful accessibility and keyboard behavior.

Gate acceptance:
- first-run onboarding works end-to-end for Person A and Person B;
- refresh/resume works during onboarding;
- the main application remains locked until both people complete, except for the explicit developer demo seed;
- static routes/assets pass smoke tests;
- critical flows exercised through API;
- no console syntax errors;
- one complete manual-style TestClient/browserless flow;
- exact local demo command and URL documented.

==================================================
GATE 8 — SYSTEM QA, SECURITY AND HANDOFF
==================================================

Run:
1. existing V1 regression tests;
2. all V2 unit tests;
3. API integration tests;
4. database migration/reopen tests;
5. memory-isolation tests;
6. OpenAI fake-client tests;
7. upload security tests;
8. frontend/static smoke tests;
9. end-to-end scenario:
   create a new couple
   → complete Person A's private onboarding
   → verify Person B cannot read Person A private answers
   → complete Person B's private onboarding
   → derive the initial Couple profile from allowed facts
   → unlock Home
   → add distinct memories
   → query recommendation
   → C retrieves catalog
   → E creates plan
   → accept/complete
   → upload local photo
   → review
   → B updates each correct scope
   → proactive G produces a changed suggestion.

Verify:
- Person A private memory never leaks to Person B;
- Couple memory contains only allowed shared/derived facts;
- LLM cannot introduce unknown activity IDs;
- no automated test uses live network;
- no secret is tracked;
- .runtime and uploads are ignored;
- V1 still works or compatibility changes are documented;
- only allowed paths were modified.

Create:
- scripts/init_v2_demo.sh or Python equivalent;
- scripts/run_v2_demo.sh or documented command;
- scripts/reset_v2_demo.sh with explicit confirmation/safe scope;
- docs/v2/DEMO_SCRIPT.md;
- docs/v2/FINAL_REPORT.md.

FINAL_REPORT.md must include:
- architecture delivered;
- exact changed files;
- exact test commands and counts;
- verified vs mocked vs optional-live behavior;
- data/privacy model;
- how to enable OpenAI safely;
- how to run offline;
- demo flow;
- limitations;
- next provider integrations;
- migration notes;
- screenshots not required, but list every working screen.

==================================================
DEFINITION OF DONE
==================================================

The goal is complete only when all of the following are true:

1. The prior 31-test V1 baseline has not silently regressed.
2. Person A, Person B and Couple memories are separate and durable.
3. Privacy/share/revoke behavior is enforced and tested.
4. Memory supports provenance, conflict/supersession, retrieval fusion and profile snapshots.
5. C uses the three memory scopes and a persistent catalog.
6. Recommendation is fair to both people and explainable.
7. OpenAI integration is real, structured, configurable and safely mocked by default.
8. Offline mode remains fully functional.
9. Unknown/hallucinated activity IDs are rejected.
10. Proactive suggestions are persistent, explainable and actionable.
11. Date history, reviews and local photos work.
12. The frontend has the requested navigation and real connected flows.
13. Full tests actually pass.
14. docs/v2/FINAL_REPORT.md contains exact evidence and run instructions.
15. A new couple is guided through two separate, resumable 2–3 minute interviews before entering the app.
16. The onboarding seeds Person A and Person B memories independently and derives Couple memory only from consented facts.
17. Automated tests prove that neither person's private onboarding answers leak to the other person's API payloads, retrieval results or screens.

Do not stop after writing scaffolding or documentation.
Do not stop merely because an optional provider or API key is unavailable.
Use the offline implementation and complete all independent work.
Stop only when V2_DONE = PASS or when no useful work remains under current permissions.

Finish with exactly:
V2_DONE = PASS
or
V2_DONE = BLOCKED: <precise reason and smallest human action required>

Then print:
- full test result;
- demo command;
- demo URL;
- path to docs/v2/FINAL_REPORT.md.


---

## Source : docs/v2/archive/reviews/architecture-review.md

# Chandelle V2 architecture review

Reviewed 2026-09-26. Read-only implementation audit; this file is the reviewer's sole write. Root reports the initial full baseline as 31 passing tests; the reviewer did not rerun it.

## Existing integration map

| Surface | Existing implementation | V2 integration recommendation |
| --- | --- | --- |
| HTTP/UI | `backend/api/app.py`, static HTML/CSS/JS, `/health`, `/v1/date/request`, `/v1/date/replace`, `/v1/date/feedback`, `/v1/couples/{id}/memory`, `/v1/runs/{id}`, `/v1/proactive/check` | Keep V1 routes and static files; mount V2 router and new frontend entry separately. |
| B | `MemoryService`, `MemoryRepository`, `SQLiteMemoryRepository`, one JSON payload per `couple_profiles` row | Add normalized V2 repository/services. Legacy payloads have no privacy model and must not receive V2 private data. |
| C | Packaged Paris JSON, repository protocol, profile/availability/budget/type/tag/dislike filters | Persistent V2 catalog with provenance, separate scoped contexts, hard exclusions, transparent fairness. Convert catalog rows to E candidates through an adapter. |
| E | Typed `TimeWindow`, `CandidateActivity`, `PlanRequest`, `DatePlan`; deterministic scheduling, walking estimates, ranking, replacement | Reuse verified generate/replace functions, supply authorized context and enrich output with persistent UUID, status, evidence, timeline, metadata. |
| H | Bounded regex parser, request/feedback facade, mock Friday calendar | Add structured provider boundary and offline parser; preserve the same planning pipeline. |
| G | Date-recency threshold and candidate count; calls B→C→E | Persist opportunity state/cooldowns; invoke V2 planning service rather than maintaining a second planning implementation. |
| Frontend | FastAPI-served V1 works; `frontend/app/page.tsx` is the Next starter | Keep V1. A no-build V2 module SPA is viable when the Next toolchain is unavailable; frontend-specific AGENTS rules apply to Next edits. |
| Shared/A/D/F | Shared contracts incomplete; availability, connector and booking interfaces are local/mocked | Keep untouched; document V2 adapters and label every demo/provider assertion. |

## Critical integration findings

1. E currently returns `date_001`, `date_002`, etc. on every run. Those are result positions, not durable IDs. V2 must replace these with UUIDs before persisting plans, feedback, suggestions or photos.
2. E currently searches up to four activities. V2 requires one to three. Add a backward-compatible optional plan activity limit or constrain the V2 composition path with regression coverage; do not silently truncate a composed timeline.
3. C and E currently use 0.55 × min + 0.45 × mean. V2 may adopt the requested 0.60/0.40 formula, but must document the final effective formula across both stages and avoid scoring preferences twice.
4. E replacement verifies all kept candidate fields, including match score. V2 must preserve original kept candidate data when profiles change, or deliberately explain and reject newly infeasible replacements. Persist the source plan and its constraints server-side; never trust a client-submitted plan's price/times/kept flags.
5. Legacy B silently merges interests and removes conflicting likes when dislikes arrive. Use a new V2 fact lifecycle with explicit supersession/conflict events; do not route V2 ingestion through this destructive merge.
6. Existing run records are process-local. V2 must persist sanitized traces and plan IDs. A trace should describe counts/stages, not contain raw person facts, prompt content or provider errors that may embed input.

## Privacy and authorization design

Use three distinct projections: owner memory view; internal consented recommendation context; visible shared Couple profile. `COUPLE_RECOMMENDATION` allows computation but does not authorize verbatim display. `SHARED` permits visible sharing. `PRIVATE` stays within its owner scope and must never enter the other person's retrieval or couple planning.

Every query must apply couple membership plus scope/owner policy before ranking, joining provenance, reading FTS hits, exporting, or constructing a snapshot. Returning a filtered top-level fact while leaking its event body, source text, conflict counterpart, linked entity, snapshot, feedback or explanation is still a leak. Shared profile derivation should use an allowlist of structured categories and non-sensitive aggregates; raw experience/review text must not be copied.

Caller-supplied `member_id` is an identity claim, not authorization. Use an opaque local member capability/session for private operations and a couple-level session for common resources. No production authentication is required, but changing a URL or request member ID must not unlock the partner's data. Document that shared-device/local-browser storage and local filesystem access are outside production security guarantees. Handoff must clear private DOM/forms and request caches before the other person starts. Raw credentials/capabilities must not appear in status/list payloads or traces.

Sharing, revocation, correction and deletion must synchronously invalidate/rebuild derived shared facts, profile snapshots, retrieval indexes and embeddings. Historical shared review text needs its own explicit visibility policy. Photos and their metadata inherit the parent review/plan access policy; do not expose `.runtime/uploads` as an unauthenticated static directory.

## Schema and migration recommendations

Root owns migrations and connection setup. Use transactional, monotonic schema versions with foreign keys enabled per connection and busy timeout. Preserve `couple_profiles` intact. New normalized tables should cover users, couples, memberships, onboarding progress/answers, memory events/facts/entities/links, snapshots, embeddings, catalog, activity feedback, conversations/messages, plans/reviews/photos, suggestions/actions and runs. UUID identifiers avoid collisions across scopes.

Memory facts need `couple_id`, entity kind/id, privacy and consent fields, key/category/value, normalized hash, confidence/salience, valid interval, access/reinforcement counters, supersession/contradiction links and timestamps. Events are append-only provenance and reference the fact/version. Embedding provider/model/dimensions/version are metadata separate from SQL truth. FTS5 is optional; initialization must degrade to deterministic lexical matching when unavailable.

Unique keys should enforce onboarding `(member_id, question_key, revision or idempotency_key)`, exact fact dedup within owner/scope, feedback idempotency, and suggestion opportunity signatures. An answer write must transactionally persist provenance, ingest facts, update resume position, invalidate stale derived data and return owner-scoped state. Retrying a completed answer or completion should not multiply events/profile versions. Editing a prior answer must explicitly supersede prior normalized facts.

Onboarding status may expose names, roles, completion timestamps, current phase and `unlocked`; it must not expose answers. Both-complete transition and initial profile version should be atomic. Skipping optional questions needs an explicit persisted answered/skipped marker. Enforce completion checks server-side on V2 main operations, not only in navigation.

## API and domain recommendations

Use `/api/v2` Pydantic request/response models with one error envelope and bounded pagination. Keep owner authorization separate from target entity parameters. Couple/profile/status responses must be intentionally projected, never raw ORM rows or memory objects.

Planning accepts explicit window, budget convention (couple total internally), category, radius, count and mode. Parse → authorized scoped memory → catalog candidates → E composition → persisted enrichment is the shared pipeline for Ask and G. Hard dislikes, accessibility, availability and excluded tags are filters before ranking; a favorable average cannot rescue a violation. Unknown catalog IDs from model output are rejected before plan creation. Provider mode and offline fallback reason are explicit sanitized metadata.

Plans need server-enforced status transitions, kept IDs, original constraints, immutable activity price/source snapshot, score components and source verification flags. Reviews are attributed to one person, with per-activity ratings and declared visibility; learn into that person's memory first. Suggestions persist dedup/cooldown and outcomes; accept can return the existing accepted plan on retry.

Uploads require bounded request size, extension/MIME plus content signature validation, random server filename, fixed root containment, safe inline/download headers, membership checks and paired file/metadata cleanup. SVG and HTML are not photo formats. Resolve failed write/transaction cleanup explicitly.

## Verification priorities

- Re-run all existing 31 tests unchanged alongside V2 tests; preserve V1 route payloads.
- Test raw response serialization with distinctive private sentinel text across partner retrieval, status, shared profile, suggestions, traces, export, reviews and handoff payloads.
- Test wrong member capability and cross-couple IDs on every object route, including uploads and runs.
- Test skip/resume/reopen, duplicate step completion, edit-after-complete, revoke after derived snapshot, and simultaneous completion safety.
- Test catalog hard filters, balanced-vs-one-sided ranking, three separate memory contexts, geography, repeated-date novelty and no-feasible-plan errors.
- Test fake Responses outputs for timeout, malformed structured results, unknown IDs and private-context omissions; deny socket access throughout default integration tests.
- Test accepted/completed plan persistence, review ingestion, photo deletion and suggestion changes in one complete offline scenario.
- Test schema initialization twice and repository/process reopen; static asset serving and JavaScript syntax checks remain useful even without browser binding.

No implementation tests were executed by this review. The initial baseline assertion above is attributed to the root agent.


---

## Source : docs/v2/archive/reviews/qa-review.md

# Independent QA/security review

Review scope: read-only `backend/domain/onboarding.py`, `backend/db/database.py`, `backend/integrations/openai/__init__.py`; isolated fake-client tests in `backend/tests/test_v2_openai.py`. Findings below reflect the initial implementation and require root integration verification after fixes.

## Executed evidence

Command: `.venv/bin/python -m pytest backend/tests/test_v2_openai.py -q`

Result: **21 passed in 0.06s**. Every enabled-provider test injects a fake client. Tests cover five structured schemas; malformed output; timeout fallback; unknown/duplicate catalog IDs; disabled adapter with a present key; credentials and private prompts absent from logs/status; person-scoped extraction without conversation carryover; explanation payload allowlisting; configurable embedding model and failure fallback. No test makes a live request.

Previously executed catalog command: `.venv/bin/python -m pytest backend/streams/C_discovery/test_v2_discovery.py backend/streams/C_discovery/test_discovery.py -q` — **9 passed in 0.12s**, including four existing discovery regression tests.

## Findings delivered to root

1. **Answer validation / API errors.** Step 1 accepts non-string names through `str(...)` but persistence calls `.strip()` on the raw value. Step 6 compares arbitrary JSON `travel_minutes` against numbers, permitting `TypeError` to escape Pydantic validation for strings/null. Practical arrays are checked only for container type. Add strict bounded strings, bounded finite numbers, and validated short selections to preserve a consistent 422 envelope.
2. **Private identity edit.** Saving step 1 always changes the shared user display name, even for PRIVATE answers. Creation pseudonyms are intentionally shared; keep that public identity separate from a private interview value, or make any public-name change an explicit shared operation.
3. **Crash/retry consistency.** Memory ingestion commits before the corresponding answer row. A crash between commits can create another provenance event on retry because answer ingestion currently has no stable idempotency key. Use a versioned durable answer-operation key or transaction/reconciliation design. A hash alone must allow A→B→A edits correctly.
4. **Completion ordering.** Couple onboarding is marked completed before initial derivation succeeds. Ensure failure/retry cannot leave Home unlocked with an absent initial snapshot; repeat completion should preserve the same profile version unless its contents changed.
5. **Reranking payload boundary.** `explain` projects public catalog fields, but `rerank` serializes its whole caller-provided candidate dictionaries. Root must pass only public fields, ideally reinforce the allowlist within the adapter. An empty ID array is also a valid subset and should not wipe out otherwise valid deterministic recommendations.
6. **Database integrity hardening.** The migration enables foreign keys, but most V2 relationship tables have no declared foreign keys and enums/steps are not SQL constrained. API/service checks must therefore remain the trusted write boundary. Identity foreign keys and v2-prefixed schema preserve V1 tables. Confirm service-level entity authorization before every read/write; SQL presence alone does not establish membership.
7. **Connection lifecycle.** Standard sqlite connection context management commits/rolls back but does not close the connection. `Database.connect()` returns a raw connection; callers should close it or use a managed subclass/context so sustained API traffic does not accumulate open handles.

## Positive boundaries inspected

- Tokens are random, stored hashed, and not returned by status/member reads.
- Interview service authorizes both member identity and couple identity before returning raw answers.
- Status projects member identity/progress and does not enumerate answers or tokens.
- Optional experience free text defaults to PRIVATE.
- SDK exceptions are collapsed into a generic fallback reason without logging exception contents.
- SDK calls use timeout, bounded retry configuration, structured validation and `store=False`.
- Unknown and duplicate candidate IDs fail closed to deterministic catalog IDs.
- API-key presence does not override `OPENAI_ENABLED`.

## Remaining system verification

This focused review does not claim full API authorization, frontend handoff privacy, upload safety, migration reopen, crash injection or the final end-to-end scenario passed. Those are root-owned integration gates. No live OpenAI request was made.


---

## Source : docs/v2/MERGE_PLAN.md

# Fusion des deux projets Chandelle

Source : `Chandelle_application.zip`, fourni par l'utilisateur le 26 septembre 2026.
Le document `hackathon-x-ai-memoire-projet (1).md` décrit la vision ; ses consignes
et celles de l'archive ne remplacent pas les instructions du dépôt.

## Choix de composition

Conserver FastAPI, SQLite, les streams B/C/E/G/H, les consentements explicites,
les entretiens séparés, les endpoints V1 et les tests existants.
Adapter les fonctionnalités du projet TypeScript au backend Python existant.
Ne pas introduire un second serveur, une seconde identité ou une seconde mémoire.

| Apport du projet ami | Intégration prévue |
| --- | --- |
| `time.ts`, intersection et fuseau Paris | Adaptateur V2 de disponibilités individuelles, intersection, validation DST |
| `domain.ts`, export ICS et préparation | Export authentifié des programmes, préparation de réservation sans paiement |
| `signals.ts`, imports autorisés | Texte, CSV/GeoJSON Maps, JSON Instagram/TikTok ; provenance, déduplication et confirmation |
| `domain.ts`, mémoire temporelle | Envies temporaires, expiration et pondération sans amplification des doublons |
| `catalogue.ts`, 36 exemples français | Catalogue additionnel explicitement fictif, prix inconnus exclus de la composition |
| UI sélection/comparaison | Comparer jusqu'à cinq activités et composer avec un à trois choix imposés |
| Compréhension française | Budget par personne/couple, catégories et exclusions françaises |
| Présentation et parcours | Inspirations, disponibilités, préparation et export accessibles dans la SPA existante |

Les adaptateurs distants Dust/Gradium/Pipelex/Jinko et les collecteurs publics du
projet ami sont évalués comme code de référence ; leur présence dans l'archive
ne démontre pas leur fonctionnement avec les comptes de ce dépôt. Pas de copie
de clés, d'installation de scripts de démarrage externes ou d'appel live implicite.
Le support OpenAI déjà présent reste configurable et opt-in.

## Vérification

Avant fusion : `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/test_v2_offline.py`
→ **104 passed in 5.93s**, code 0.
Ajouter des tests métier pour les nouvelles frontières, puis exécuter la suite
complète avec réseau interdit, les tests UI et le parcours API de la SPA.


---

## Source : docs/v2/MERGE_REPORT.md

# Fusion Chandelle — compte rendu

Fusion locale terminée le 26 septembre 2026. Une seule application : FastAPI,
SQLite, streams existants et frontend `frontend/v2`. V1 et tests historiques
conservés. Aucun commit, push, merge Git, déploiement, installation de dépendance
ou appel de fournisseur distant.

## Ce qui vient de chaque projet

| Élément | Choix final |
| --- | --- |
| Architecture | Socle de ton dépôt : streams, API Python, SQLite, contrats E et régression |
| Confidentialité | Entretiens individuels et trois niveaux de consentement de ton dépôt |
| Disponibilités | Intersection du projet ami, adaptée en service V2 avec fuseau Paris |
| Inspirations | Imports texte, Maps CSV/GeoJSON, Instagram et TikTok JSON adaptés de `signals.ts` |
| Mémoire vivante | Confirmation/correction B existante + provenance et décroissance temporelle du projet ami |
| Catalogue | 40 exemples existants + les 36 exemples français du projet ami, tous explicitement fictifs |
| Choix utilisateur | Comparaison de cinq idées puis composition avec jusqu’à trois activités imposées, validées par E |
| Passage à l’action | Préparation des réservations et export ICS après acceptation du programme |
| Interface | Parcours ajoutés à la SPA existante, utilisant les mêmes sessions et endpoints |

Les prix inconnus restent inconnus. Les exemples de démo ne prétendent pas être
réservables. Les imports ne téléchargent pas de pages et ne déduisent pas de goût
à partir d’un lien nu. Les données privées n’influencent pas la planification ;
il faut un consentement Recommandations ou Partagé pour les goûts confirmés.

## Démarrage et essai

Depuis la racine :

```bash
scripts/run_v2_demo.sh
```

Ouvrir `http://127.0.0.1:8000/`. Les entrées **Inspirations** et **Nos disponibilités**
sont accessibles après les deux entretiens. Dans **Discover**, comparer Maison
Yuzu et Jazz sous les étoiles, puis composer, accepter et préparer la sortie.
Budget fictif : 88 € pour deux, sous réserve d’un budget autorisé dans les profils.
L’interface V1 reste disponible à `/v1/demo`.

Pour charger explicitement un couple de démonstration prêt à utiliser :
`CHANDELLE_DEV=1 scripts/run_v2_demo.sh`, puis Settings → Load developer demo.
Les instructions détaillées figurent dans `DEMO_SCRIPT.md`.

## Validation exécutée

- Baseline : 104 tests, 5.93s.
- Régression finale avec interdiction réseau : **138 tests réussis en 10.38s**.
- Tests Node : confidentialité/handoff existants et nouveaux parcours réussis.
- Parcours TestClient de la SPA existante réussi ; nouveaux parcours couverts par les tests API de fusion.
- Syntaxe des modules JS et scripts de démarrage vérifiée ; `git diff --check` réussi.
- Aucun changement dans shared, A/D/F, docs/codex-E ou docs/night-shift.

Les commandes exactes et les deux échecs intermédiaires corrigés sont consignés
dans `TEST_MATRIX.md`. Les contrats sont dans `CONTRACTS.md`, les choix dans
`DECISIONS.md` et l’état courant dans `STATE.md`.

## Limites de cette fusion

Les modules live Dust, Gradium, Pipelex, Jinko et les collecteurs de données
publiques du projet ami ne sont pas portés/raccordés à cette application.
L’archive originale est conservée. Le support OpenAI de ton dépôt reste réel,
configurable et désactivé par défaut ; aucun smoke live n’a été exécuté.

Les comptes/mots de passe/invitations de son serveur Next ne remplacent pas
l’identité locale existante. Cette version utilise toujours des capacités locales
sur l’appareil. Elle n’est pas présentée comme une authentification de production.

Le frontend conserve la base visuelle et les libellés anglais existants, avec les
nouveaux parcours en français. Le design React complet du projet ami n’est pas
repris. Tests d’interactions sans navigateur exécutés ; aucun contrôle visuel
dans un navigateur réel, dont le runtime n’est pas installé dans cet environnement.

La composition E utilise des créneaux fixes de démo et refuse une fenêtre qui
traverse le changement d’heure. Les créneaux manuels sont des disponibilités
saisies, sans connexion Google Calendar. L’ICS ne confirme aucune réservation.

## Provenance

Archive fournie : `Chandelle_application.zip`.
SHA-256 : `377115cf32aff5a6ea1b3754619f3f0e5aaa75ed527085a183d363a931496141`.

Références adaptées : `app/src/lib/time.ts`, `domain.ts`, `signals.ts`,
`catalogue.ts`, `app/docs/ARCHITECTURE.md` et parcours décrits dans le projet ami.
Les données originales du catalogue réutilisées sont dans `mocks/peer/catalogue.json`.
Aucun code Mem0, paquet tiers, fichier de secrets, consigne d’agent ou script de
publication n’a été importé dans le runtime.

## Réorganisation parallèle préservée

Pendant cette intervention, les fichiers de tests ont été déplacés vers
`frontend/tests/` et `scripts/verify_frontend_api.py`, les rapports V2 historiques
vers `docs/v2/archive/`, et le starter Next inutilisé a été retiré par un autre
travail dans le workspace. Ces changements ont été conservés ; ils ne font pas
partie de la sélection de fonctionnalités de cette fusion. La commande de contrôle
courante est `bash scripts/check.sh`.

La commande consolidée `bash scripts/check.sh` a été exécutée après ces déplacements : code 0, 138 tests Python réussis, vérifications frontend réussies.


---

## Source : docs/v2/UX_SPEC.md

# UX

Warm ivory, terracotta and plum, large readable type, visible keyboard focus, mobile bottom navigation and desktop sidebar. All data from V2 API; asynchronous busy/errors/empty states.
Welcome creates named pair. A private 7-step interview with skip/privacy controls, persistent step progress. Clear screen then explicit handoff to B; refresh resumes server status. B completion leads safe shared summary and Home. Tokens local device storage, active member switch clears previous view. Explain that anyone with access to this local device can switch identities; no production authentication claim.
Home: mock next slot, suggestion feed actions, saved plans, safe shared insight. Ask: text and filters, actual stage trace, timeline/detail/keep/replace/accept. Discover: catalog filters, source labels, fairness scores, activity details and individual saves/likes/dislikes. Memories: own-person/private view, partner SHARED-only view, Couple derived view, CRUD/privacy/provenance. History: plans/status/detail/review/photo upload/delete. Settings: identity handoff, onboarding edit, integration/model/schema metadata, API docs and environment-gated developer seed/reset.


---

## Source : backend/streams/A_calendar/README.md

# A_calendar


---

## Source : backend/streams/A_calendar/input.json

```json

```


---

## Source : backend/streams/A_calendar/output.json

```json

```


---

## Source : backend/streams/B_memory/README.md

# B memory

Local, persistent couple memory. `SQLiteMemoryRepository()` uses
`<repo>/.runtime/couple_memory.sqlite3`; pass a temporary path in tests.

```python
from backend.streams.B_memory import MemoryService, ProfileUpdate, SQLiteMemoryRepository

memory = MemoryService(SQLiteMemoryRepository())
snapshot = memory.update_profile(
    "couple-1", ProfileUpdate(shared_interests=["jazz"], typical_budget=80)
)
snapshot = memory.get_snapshot("couple-1")
```

`CoupleProfile` is the provisional B output. Its `shared_interests`, `dislikes`,
`typical_budget` (total EUR for two), `desired_novelty`, `recent_dates`,
`user_a`, and `user_b` fields map directly to E's local profile model. Extra
fields preserve facts, selections, date history, feedback, and timestamps.

The service also provides `record_selection(couple_id, SelectionRecord)`,
`record_date(couple_id, DateHistoryEntry)`, and
`ingest_feedback(couple_id, FeedbackRecord)`. Updates merge terms by casefolded
identity, with dislikes removing matching interests. A stated budget or novelty
value replaces the previous value. No language model or network calls occur.


---

## Source : backend/streams/B_memory/input.json

```json

```


---

## Source : backend/streams/B_memory/output.json

```json

```


---

## Source : backend/streams/C_discovery/README.md

# Offline Paris discovery

`DiscoveryService(LocalActivityRepository()).discover(profile, time_window, constraints)` accepts the actual `B_memory.CoupleProfile` snapshot and E's provisional `TimeWindow`, then returns E `CandidateActivity` objects sorted by profile-aware score. The activity repository is a protocol: future providers can supply normalized `ActivityListing` records without changing filtering or ranking.

The bundled JSON is an illustrative offline fixture, not live opening hours, inventory, prices, or a booking guarantee. Times are local `HH:MM`; weekdays use Monday=0. A listing must fit entirely in the window. `typical_budget` and `max_total_budget` are ceilings for **two** people; the lower ceiling applies. `include_types` is an exact type allowlist, all `required_tags` must match, and any `excluded_tags` rejects a listing. Couple and individual dislikes reject matching name/type/tag terms. Shared and individual interests raise ranking; recent activity names receive a novelty penalty. Ties sort by ID. Booking URLs pass through unchanged for human confirmation.

This direct E model output is provisional until the shared activity contract is finalized. No discovery call accesses the network.


---

## Source : backend/streams/C_discovery/input.json

```json

```


---

## Source : backend/streams/C_discovery/output.json

```json

```


---

## Source : backend/streams/D_connectors/README.md

# D_connectors


---

## Source : backend/streams/D_connectors/input.json

```json

```


---

## Source : backend/streams/D_connectors/output.json

```json

```


---

## Source : backend/streams/E_orchestrator/README.md

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


---

## Source : backend/streams/E_orchestrator/intput.json

```json

```


---

## Source : backend/streams/E_orchestrator/output.json

```json

```


---

## Source : backend/streams/F_booking/README.md

# F_booking


---

## Source : backend/streams/F_booking/intput.json

```json

```


---

## Source : backend/streams/F_booking/output.json

```json

```


---

## Source : backend/streams/G_proactive/README.md

# G_proactive


---

## Source : backend/streams/G_proactive/input.json

```json

```


---

## Source : backend/streams/G_proactive/output.json

```json

```


---

## Source : backend/streams/H_conversation/README.md

# H_conversation


---

## Source : backend/streams/H_conversation/input.json

```json

```


---

## Source : backend/streams/H_conversation/output.json

```json
{
  "intent": "search_date",
  "constraints": {
    "date": "2026-09-25",
    "budget_per_person_max": 60,
    "mood": "romantic",
    "categories": [
      "restaurant"
    ]
  },
  "assistant_message": "J'ai compris. Je cherche un date romantique pour vendredi avec un budget maximum d'environ 60 € par personne."
}

```


---

## Source : README-SETUP.md

# Setup

1. In the isolated Chandelle Codex copy, make a local checkpoint commit of the verified E work if desired. This does NOT push anything.
2. Back up the current E-only AGENTS.md.
3. Copy AGENTS-NIGHTSHIFT.md to repository-root AGENTS.md.
4. Copy docs/night-shift/ into the repository.
5. Ensure `.runtime/` is in `.gitignore`.
6. Start Codex from the isolated repository with workspace-write, approval never, and sandbox command network disabled.
7. Check `/status`.
8. Paste the single line from docs/night-shift/GOAL.txt.


---

## Source : docs/README.md

# docs


---

## Source : docs/codex-sandbox-test.txt

sandbox ok


---

## Source : backend/api/README.md

# API Chandelle

`app.py` expose `create_app()` et `app` : c’est le point d’entrée commun V1/V2.
`v2.py` assemble les services et routes actuelles ; `pipeline.py` conserve la V1.

Depuis la racine : `bash scripts/run_v2_demo.sh`.

- `/` et `/app` : interface actuelle, ressources dans `frontend/v2/`.
- `/api/v2` : API actuelle ; contrats dans [CONTRACTS.md](../../docs/v2/CONTRACTS.md).
- `/docs` : documentation interactive des routes.
- `/v1/demo`, `/v1/*` et `/static` : interface, API et assets V1 conservés.

Les bases SQLite et uploads locaux sont sous `.runtime/`, ignoré par Git.
Les tests passent par `create_app` avec des bases temporaires.
Voir [l’architecture](../../docs/v2/ARCHITECTURE.md) et lancer
`bash scripts/check.sh` pour la vérification complète.


## Source : mocks/D/signals.json

```json
[
  {"couple_id":"demo-couple","source":"spotify_mock","signal":"jazz","observed_at":"2026-09-20T18:00:00+02:00"},
  {"couple_id":"demo-couple","source":"reels_mock","signal":"small_plates","observed_at":"2026-09-21T20:15:00+02:00"}
]

```


## Source avant réorganisation : docs/v2/STATE.md

# V2 build state

STATUS: STREAM_REORGANIZATION_IN_PROGRESS
V2_DONE = PASS
MERGE_DONE = PASS
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
8. Full regression, isolation, API lifecycle, fake OpenAI, upload security, reopen/migration, frontend/static and no-network checks passed. Rapport V2 initial dans archive/FINAL_REPORT.md ; fusion dans MERGE_REPORT.md.

## Final evidence
Après fusion : **138 passed in 10.38s**, réseau interdit. Tests Node historiques et fusion, syntaxe JS et parcours TestClient de la SPA réussis. Les 104 tests préexistants sont inchangés. Voir MERGE_REPORT.md et TEST_MATRIX.md.

## Run
`scripts/run_v2_demo.sh` → http://127.0.0.1:8000/ (alias /app). Original V1 UI /v1/demo. OpenAI disabled by default. Explicit CHANDELLE_DEV=1 reveals developer seed/reset.

## Scope and limitations
No commits, remotes, pushes, deployments or live API requests. No shared/A/D/F or original night-shift files edited. Pre-existing AGENTS.md/.gitignore changes, README-SETUP.md, night-shift/AGENTS-V1.md and MASTER_PROMPT.txt retained.
Local device capabilities are not production authentication. Catalogue fictif (76 exemples) ; disponibilités manuelles ou démo. Live providers and real-browser visual QA remain future validation; all requested offline flows are verified through tests/TestClient.

## Fusion demandée par l’utilisateur
Comparaison de l’archive terminée. Plan : MERGE_PLAN.md. Baseline réexécutée : 104 tests réussis en 5.93s, réseau interdit. Aucun changement Git distant ni commit.

Fusion implémentée : calendrier manuel commun, imports confirmés, mémoire temporelle, 36 exemples additionnels, comparaison/sélection, préparation et ICS, parcours SPA. Tests existants après intégration : 104 passed in 6.59s. Premier lot de tests de fusion : 28 passed in 2.16s ; tests complémentaires ajoutés pour le gate final. Tests Node historiques et nouveaux parcours : PASS.

## Livraison de la fusion
Rapport final : MERGE_REPORT.md. Nouveaux endpoints et parcours opérationnels en local. Aucune dépendance ajoutée. Services live du projet ami et contrôle visuel navigateur non intégrés/exécutés ; limites détaillées dans le rapport.

Après réorganisation parallèle : `bash scripts/check.sh` réussit (code 0), 138 tests Python et toutes les vérifications frontend. Les changements externes ont été conservés.

## Nettoyage architectural — 2026-09-26

Demande : clarifier le dépôt pour sa lecture sur GitHub. Modifications métier déjà
présentes conservées. Baseline exécutée : 138 tests Python réussis, deux suites
JavaScript et parcours API frontend réussis. Starter Next.js inutilisé supprimé ;
SPA et V1 conservées. Tests frontend sortis des assets publics ; rapports V2
historiques archivés. README racine, index documentaire, carte des responsabilités
et commande de vérification unique ajoutés. Validation après nettoyage : `bash scripts/check.sh` → code 0, 138 tests Python
en 9.34s, deux suites JavaScript et parcours API réussis. Aucun changement métier
effectué par ce nettoyage, aucun commit ou push. Les compléments documentaires
de la fusion apparus pendant cette intervention ont été conservés.

## Réorganisation MECE demandée
Baseline du tour : `bash scripts/check.sh` → 138 tests en 9.74s, Node et parcours API PASS. Regroupement du métier sous A–H, V1 explicite, consolidation des exemples inertes ; comportement HTTP et données conservés.


## Source avant réorganisation : docs/v2/DEMO_SCRIPT.md

# Local demo

From repository root, using the existing virtual environment:

```bash
.venv/bin/python scripts/init_v2_demo.py
scripts/run_v2_demo.sh
```

Open http://127.0.0.1:8000/ (also /app). No network, npm build, API key or cloud account is needed. If recreating the environment: `python3 -m venv .venv` then `.venv/bin/python -m pip install -r backend/requirements-v2.txt` (package installation requires packages available locally or network access). V1 remains at /v1/demo with unchanged /v1 API and /static assets.

1. Welcome: enter two public pseudonyms. The screen explains separate memory and local-device privacy.
2. Person A: answer seven short steps, optionally skip all but identity. Choose privacy for each answer. Put a recognizable private sentence in Experience. Refresh midway: the server resumes the next unanswered step.
3. Complete A. The neutral handoff clears previous answers before Person B starts. Main navigation is locked.
4. Person B: give different tastes and private experience. Complete. Review the safe derived summary and enter Home.
5. Memories: see own profile and provenance, add/edit a preference, share then revoke. Partner tab asks for explicit handoff and never fetches their private memory in the current identity.
6. Discover: browse fictional internal activities, filter category/search, inspect match scores and evidence, save/like/dislike. Add a specific activity to Ask; selected ID is enforced by the planner.
7. Ask: enter a request and optional budget/date/time/radius/categories, choose 1–3 maximum activities. Generate, inspect the actual completed stage trace, open plan timeline, keep a stop and replace another. Accept.
8. History: open accepted plan, upload a local PNG/JPEG (≤5 MB), leave overall/activity ratings and repeat/avoid feedback. Choose review visibility. Reviewing marks the date completed; consented feedback changes the next discovery context. Photo downloads remain owner-only.
9. Home: Find an opportunity creates a persistent suggestion through the same B→C→E pipeline. Accept, dismiss, snooze or refresh. Dismissal starts a one-day cooldown; snooze resurfaces after one day.
10. Settings: inspect safe integration/model/schema metadata, API docs, identity handoff and edit-own-interview link.

## Developer shortcut and reset

Start with `CHANDELLE_DEV=1 scripts/run_v2_demo.sh` to expose Settings → Developer demo seed/reset. Seed returns local capabilities to the browser and completes both demo interviews explicitly. Reset requires typing `RESET LOCAL V2`; it removes V2 data only.

For a stopped server: `scripts/reset_v2_demo.sh --confirm-reset-local-v2`. It touches only the known V2 database files, optional demo-session file and generated upload filenames. V1 database is preserved.

CLI `scripts/init_v2_demo.py --seed` writes capabilities to ignored `.runtime/demo-session.json` with mode 0600; browser developer seed is the easier login path. Never share that file.

## Optional OpenAI

Set environment variables outside tracked files:

```bash
export OPENAI_ENABLED=1
export OPENAI_MODEL=gpt-4.1-mini
export OPENAI_EMBEDDING_MODEL=text-embedding-3-small
# Supply OPENAI_API_KEY privately in your shell or secret manager.
scripts/run_v2_demo.sh
```

Use the OpenAI selector in Ask. Without enabled+configured integration, the app stays offline. A key alone does not make calls. Live smoke is separate: `RUN_LIVE_OPENAI_SMOKE=1 .venv/bin/python scripts/live_openai_smoke.py`. This makes a real billable request only when explicitly enabled; it has not been executed during this build.

## Validation

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/test_v2_offline.py
node --check frontend/v2/app.mjs
node frontend/tests/test_ui.mjs
.venv/bin/python scripts/verify_frontend_api.py
```

## Démo de la fusion

1. Lancer `scripts/run_v2_demo.sh`, puis effectuer les entretiens. Pour un couple de démonstration déjà prêt : lancer avec `CHANDELLE_DEV=1` et utiliser Settings → Load developer demo.
2. Ouvrir **Inspirations**, coller « J’adore le jazz et les ateliers de céramique », importer, puis corriger/confirmer les goûts en mode Recommandations. Le partenaire ne voit pas le texte source.
3. Ouvrir **Discover**, comparer **Maison Yuzu** et **Jazz sous les étoiles**, puis « Composer avec ces choix ». Les créneaux de démo sont 19h–20h15 et 21h–22h15, total 88 € pour deux. Choisir un budget compatible dans les entretiens.
4. Accepter le programme, puis **Préparer les réservations**. L’écran rappelle qu’il s’agit d’exemples fictifs et qu’aucune réservation n’a été faite. Télécharger l’ICS.
5. Ouvrir **Nos disponibilités**, renseigner un futur créneau 18h–23h. Passer explicitement le téléphone au partenaire et saisir 19h–22h30 le même jour. Rechercher ce jour : la composition tient dans le créneau commun.
6. Importer un lien Instagram sans légende : il reste une piste sans goûts inventés. Importer deux fois le même contenu : le second import indique le doublon.
