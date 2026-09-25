# Stream E preflight — rerun 2026-09-25

AGENTS.md was reread in this isolated checkout. Its allowed write paths are `backend/streams/E_orchestrator/`, `mocks/E/`, and `docs/codex-E/`; work stays in those paths. Its dependency and test lines contain duplicated/corrupted fragments, so implementation follows the legible required capabilities and the user's explicit contract examples.

The A/B/C/E stream JSON files and shared `activity.json` and `date-plan.json` are still zero bytes. The populated shared `couple-profile.json` and `time-widow.json` are examples with different field names and an offset-aware time window. These are an **integration gap, not an implementation blocker**: Stream E uses documented provisional E-local Pydantic models and adapters. It does not claim team-wide contract compatibility until shared schemas are finalized.

Environment rerun: `.venv` imports FastAPI 0.141.1, Pydantic 2.13.5, httpx 0.28.1, and pytest 9.1.1. The permitted `docs/codex-E/` write/remove smoke check passed. `git remote -v` returned no configured remotes. No forbidden path was modified.

Decision: proceed with deterministic local implementation and tests. Integration validation against finalized A/B/C/shared schemas remains pending.
