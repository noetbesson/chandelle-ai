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
node frontend/v2/test_ui.mjs
.venv/bin/python frontend/v2/verify_api.py
```
