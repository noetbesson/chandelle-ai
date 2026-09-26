# Chandelle V2 — autonomous build rules

You are working in the isolated local Chandelle repository copy. Preserve the verified overnight V1 and evolve it into a substantially more complete product.

## Safety and source control
- Do not push, pull, add/change a Git remote, deploy, publish, purchase, or merge.
- Do not weaken sandbox permissions.
- Do not expose or commit secrets.
- Do not delete the current working V1 merely to simplify the rewrite.
- Existing tests are regression constraints.
- A local Git commit/checkpoint is allowed only if the human has already enabled it; never push it.

## Writable scope
You may create or modify:
- frontend/
- backend/api/
- backend/streams/B_memory/
- backend/streams/C_discovery/
- backend/streams/E_orchestrator/ only for demonstrated integration defects or backward-compatible improvements
- backend/streams/G_proactive/
- backend/streams/H_conversation/
- backend/integrations/
- backend/domain/
- backend/db/
- backend/tests/
- mocks/
- docs/v2/
- scripts/
- .gitignore
- dependency manifests only when genuinely needed

Read but do not silently rewrite:
- backend/shared/
- backend/streams/A_calendar/
- backend/streams/D_connectors/
- backend/streams/F_booking/
- docs/codex-E/
- docs/night-shift/

If incomplete shared contracts block integration, use explicit V2 adapters and document the gap instead of changing team-wide contracts.

## External services
Default automated tests and demo mode must work without network access.

OpenAI support must be real code behind an adapter, but:
- no automated test may make a real API request;
- do not make live API calls merely because a key exists;
- live smoke requires an explicit environment flag such as RUN_LIVE_OPENAI_SMOKE=1;
- all models must be configurable through environment variables;
- never log prompts containing private memory or API keys.

Mem0 may inspire the design, but do not clone/vendor/copy its code. Build a clean memory interface with:
1. a native local backend that always works;
2. an optional Mem0-compatible adapter boundary for later use.

## Development discipline
- Use durable build memory under docs/v2/.
- Reread STATE.md, DECISIONS.md, CONTRACTS.md and TEST_MATRIX.md before each major gate.
- Update STATE.md after meaningful work.
- Record architecture decisions in DECISIONS.md.
- Record exact test commands/results in TEST_MATRIX.md.
- Never claim a test passed unless executed.
- After three failed attempts on the same blocker, document it, choose a fallback, and continue independent work.
- Prefer backward-compatible migrations and APIs.
- No frontend-only fake success states: the UI must call actual local endpoints.

## Root-agent ownership
The root agent owns:
- architecture and contracts;
- database migrations;
- cross-stream integration;
- final API composition;
- final regression suite;
- final report.

Native subagents may be used for independent, disjoint paths only. Never let two agents edit the same files concurrently.
