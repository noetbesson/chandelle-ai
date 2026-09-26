# Chandelle — Night Shift autonomous build rules

You are working in an isolated local copy of the Chandelle repository.

## Mission
Build an offline-first backend V1 that connects the project's core agentic streams around the already-verified Stream E Date Orchestrator.

The overnight V1 must demonstrate this loop:

user request / mock conversation
→ persistent couple memory (B)
→ activity discovery (C)
→ date orchestration (E)
→ proactive opportunity logic (G)
→ conversation / feedback loop (H)
→ persistent memory update

A, D and F may be represented by adapters/mocks inside backend/api/ and mocks/. Do not modify their stream directories.

## Allowed writes
You may create or modify:
- backend/streams/B_memory/
- backend/streams/C_discovery/
- backend/streams/E_orchestrator/  # only when integration exposes a real bug; preserve existing behavior/tests
- backend/streams/G_proactive/
- backend/streams/H_conversation/
- backend/api/
- mocks/
- docs/night-shift/
- .gitignore                     # only to keep runtime/secrets/build artifacts untracked

## Read-only
Do not modify:
- frontend/
- backend/streams/A_calendar/
- backend/streams/D_connectors/
- backend/streams/F_booking/
- backend/shared/
- docs/codex-E/ except reading it

## External actions
Do not:
- commit
- push
- pull
- add or change git remotes
- deploy
- make purchases
- use paid external APIs
- weaken sandbox restrictions
- put secrets in files
- change machine-level settings

Use only the dependencies already available unless a dependency is genuinely necessary. If an installation would require network access, prefer the standard library or an existing dependency.

## Durable build memory
The files under docs/night-shift/ are the durable project memory for this run.

Maintain these continuously:
- STATE.md: current phase, completed work, blockers, next action, latest test evidence
- DECISIONS.md: append-only architectural decisions and reasons
- CONTRACTS.md: provisional internal interfaces and mappings to empty/incomplete shared contracts
- HANDOFFS.md: outputs passed from one stream/phase to the next
- TEST_MATRIX.md: acceptance criteria and actual evidence
- FINAL_REPORT.md: final human handoff

Before starting a new phase, reread STATE.md, DECISIONS.md and CONTRACTS.md.
After each meaningful phase, update STATE.md and HANDOFFS.md.
Never treat conversation context alone as durable memory.

## Product memory
Implement real local persistence for B using a repository abstraction.

Default local implementation:
- SQLite database under .runtime/
- database file must not be tracked by Git
- tests use a temporary database

Persist at minimum:
- individual user preference facts
- couple profile
- shared interests and dislikes
- budgets / novelty preference where available
- date history
- explicit selections/rejections
- post-date feedback
- simple provenance/timestamp metadata

Do not store secrets.

## Provisional contracts
The shared JSON contracts are currently incomplete/empty.
Do not modify them.

Create provisional integration models/adapters locally, and document them in docs/night-shift/CONTRACTS.md.
Make the boundary easy to replace when team contracts are finalized.

The existing Stream E local models and tests are working evidence. Preserve them.

## Stream responsibilities

### B — Memory
Build persistent memory with:
- Pydantic/domain models
- repository interface
- SQLite implementation
- deterministic profile update/merge logic
- feedback ingestion
- date-history ingestion
- query/snapshot methods
- optional LLM adapter boundary for later extraction, with deterministic/mock default

B must emit a stable CoupleProfile snapshot consumed downstream.

### C — Discovery
Build an offline/local discovery engine with:
- activity repository interface
- realistic local Paris activity fixtures
- deterministic filtering by time, budget, type/tags and dislikes
- ranking hooks that can use CoupleProfile
- clear adapter boundary for future real providers

C must consume the B profile snapshot and emit candidates suitable for E.

### E — Date Orchestrator
Already implemented and tested.
Treat E as an existing component.
Only change it to fix a demonstrated integration defect.
Preserve its existing tests.

### G — Proactive
Build opportunity detection using:
- mock/common availability
- B memory/profile
- time since previous date
- relevant candidate availability from C

Return an explainable opportunity decision.
If triggered, it may invoke the integrated B→C→E pipeline to produce a DatePlan.

### H — Conversation and Feedback
Build a simple conversation/application service:
- accept a natural-language date request plus couple id and optional explicit constraints
- deterministic/mock constraint parser for tests
- optional OpenAI adapter boundary for later real extraction
- call B → C → E in order
- return DatePlan plus a compact trace
- accept feedback and persist it through B
- expose memory snapshot for demo/debug

## Composition API
backend/api/ owns the integration/composition layer.

Expose a minimal FastAPI application with endpoints equivalent to:
- GET /health
- POST /v1/date/request
- POST /v1/date/feedback
- GET /v1/couples/{couple_id}/memory
- POST /v1/proactive/check
- GET /v1/runs/{run_id}

Exact names may differ if documented.

The main request flow must be:
H parses request
→ B loads/updates persistent couple context
→ C discovers candidates using B output
→ E composes DatePlan
→ H returns response and trace

Do not bypass B or C in the integration test.

## Mock boundaries
Tonight, external systems stay mocked/local:
- Google Calendar / A: local availability fixture
- D connectors / Reels / Spotify: local normalized fixture
- real place/event providers: local Paris fixture
- F booking: preserve booking URLs from activities and mark human confirmation required
- Dust: adapter/interface only
- Pipelex: adapter/interface only
- OpenAI: adapter/interface only; no real API call in default tests
- Gradium/Jinko: out of the overnight core path

## Multi-agent/delegation policy
If this Codex session exposes native subagent collaboration tools, use them only for independent, bounded work.

Preferred allocation:
1. memory worker → backend/streams/B_memory/
2. discovery worker → backend/streams/C_discovery/
3. QA/reviewer worker → tests/review across completed outputs without owning integration files

The root agent owns:
- backend/api/
- G
- H
- integration contracts
- cross-stream fixes
- final end-to-end verification

Do not have multiple agents edit the same files concurrently.
Do not depend on subagents being available. If collaboration tools are absent, execute the same gated plan yourself.

## Ordered gates
Do not skip gates.

GATE 0 — Audit/checkpoint
- rerun existing E tests
- inspect current tree
- initialize durable memory files
- record baseline

GATE 1 — B persistent memory
- implement
- tests pass
- write B output contract/handoff
Only then may downstream work depend on B.

GATE 2 — C discovery consuming B
- consume B CoupleProfile output
- implement realistic fixtures/repository/filtering/ranking
- tests pass
- write C output handoff

GATE 3 — Core B→C→E pipeline
- compose dependencies in backend/api/
- one mocked request returns a valid DatePlan
- no bypass of B/C
- tests pass

GATE 4 — H conversation + feedback
- natural-language/mock request path
- feedback updates B persistence
- restart/persistence test
- tests pass

GATE 5 — G proactive
- explainable trigger
- can produce a DatePlan through the same pipeline when triggered
- tests pass

GATE 6 — System QA
- full test suite
- clean-process persistence test
- end-to-end scenario
- error-path scenario
- verify no external calls
- verify allowed file scope
- documentation and final report

## Engineering rules
Prefer deterministic code for:
- scoring
- dates/times
- budgets
- overlap
- persistence
- validation
- trigger thresholds

LLM boundaries are for language understanding, explanation, and future orchestration—not deterministic arithmetic.

Never claim a test passed unless actually executed.
After three reasonable failures on the same blocker:
- record it in STATE.md
- choose a valid fallback if available
- continue independent work
- stop only if no useful work remains

## Definition of done
The overnight goal is complete only when:
1. Existing E tests still pass.
2. B persists couple memory across process/repository reopen.
3. C consumes B's profile and returns valid candidates.
4. A request flows B→C→E and returns 1–3 DatePlans.
5. Feedback changes persisted B memory.
6. G can explain and trigger a proactive recommendation using the same pipeline.
7. FastAPI exposes the integrated demo path.
8. No default automated test uses external network or a paid API.
9. Full test suite is executed successfully.
10. docs/night-shift/FINAL_REPORT.md accurately distinguishes verified, mocked, provisional and remaining integration work.
