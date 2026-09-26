# Night Shift Test Matrix

| Requirement | Test/evidence | Status |
|---|---|---|
| Existing E regression suite passes | `python -m pytest backend/streams/E_orchestrator -q`: 13 passed | PASS |
| B persists across repository/process reopen | B reopen test and separate Python-process test passed | PASS |
| B merges feedback without losing profile | B focused suite: feedback/history/reopen and merge tests passed | PASS |
| C consumes B profile | C focused test changes order and scores from actual B profile | PASS |
| C respects dislikes/budget/time | C focused tests cover dislikes, budget, time, weekday, types, tags | PASS |
| B→C→E produces DatePlan | `backend/api/test_pipeline.py`: 1 passed; checks B/C/E trace, persistence and full budget | PASS |
| Feedback updates persistent B | H test records feedback and reopens repository | PASS |
| H request path works with mock parser | H/API focused suite 4 passed | PASS |
| G proactive decision is explainable | G tests cover recency threshold and no candidates | PASS |
| Triggered G can call same pipeline | G and API tests assert B/C/E trace and plan | PASS |
| FastAPI health works | API test returned `{"status":"ok"}` | PASS |
| Integrated API request works | API test asserted B/C/E trace and 1–3 plans | PASS |
| Error path records useful status | API test asserted 422 and failed run record | PASS |
| No default test uses external network | End-to-end test monkeypatches socket connect to fail; passed | PASS |
| Full suite passes | Final `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider`: 31 passed in 0.50s | PASS |

## Demo UI final gate

| Requirement | Test/evidence | Status |
|---|---|---|
| FastAPI serves clickable Chandelle UI | API test and manual in-process smoke: `/` 200 HTML | PASS |
| UI uses live request, replacement, feedback, memory and proactive APIs | API tests exercise paths; JS references all live routes | PASS |
| Static routes smoke and final regression | Manual HTML/CSS/JS smoke 200; `node --check` passed; 31-test suite passed | PASS |
