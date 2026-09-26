# Chandelle offline API and demo

From the repository root, run:

```bash
.venv/bin/python -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/**. The page calls the local API for date requests, replacements, feedback, memory and proactive checks. No frontend build is needed. SQLite memory lives in `.runtime/couple_memory.sqlite3` and is ignored by Git.

The default availability is the next Friday 19:00–23:15 in Paris. Try “A cozy jazz date under €80” with couple name `demo-couple`. Feedback buttons save rating and activity types to memory. Booking links, when present, require human confirmation. Local provider listings are illustrative and should be verified before any real booking.

API routes: `GET /health`, `POST /v1/date/request`, `POST /v1/date/replace`, `POST /v1/date/feedback`, `GET /v1/couples/{couple_id}/memory`, `POST /v1/proactive/check`, `GET /v1/runs/{run_id}`.
