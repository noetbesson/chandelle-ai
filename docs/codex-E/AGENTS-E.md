# Chandelle Stream E

Work only in this isolated repository copy.

Allowed writes:
- backend/streams/E_orchestrator/
- mocks/E/
- docs/codex-E/

Do not modify:
- frontend/
- backend/shared/
- backend/streams/A_calendar/
- backend/streams/B_memory/
- backend/streams/C_discovery/
- backend/streams/D_connectors/
- backend/streams/F_booking/
- backend/streams/G_proactive/
- backend/streams/H_conversation/

Do not commit, push, pull, deploy, add git remotes, use paid APIs, or broaden permissions.

Build Stream E: Date Orchestrator.

Inputs:
- available time window
- couple profile / preferences
- candidate activities
- optional natural-language constraints

Output:
- 1 to 3 DatePlan objects

Required capabilities:
- filter impossible activities
- respect time and budget
- avoid overlaps
- score both users fairly
- compose coherent multi-activity dates
- explain recommendations
- replace one activity while preserving kept activities
- expose FastAPI endpoints
- provide run supervision/status- provide provide mock/local data repository a- provide run supervision/status- provide ada- provide run  O- provide run supervision/statusin- providee for scoring, dates, budgets, ove- providection and validation.
Use LLM only for composition/explanations where useful.

Run tests yourself.
Never claim a test passed unless actually executed.
After 3 failed attempts on one blocker, document it and continue other useful work.

Write:
- backend/streams/E_orchestrator/README.md
- docs/codex-E/AVANCEMENT.md
- docs/codex-E/RAPPORT-FINAL.md
