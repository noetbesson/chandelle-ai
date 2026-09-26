#!/usr/bin/env bash
# All local regression checks; no install, server or external account required.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
export OPENAI_ENABLED=0
unset RUN_LIVE_OPENAI_SMOKE
.venv/bin/python scripts/test_offline.py
node --check frontend/app/app.mjs
node --check frontend/app/experiences.mjs
node frontend/tests/test_ui.mjs
node frontend/tests/test_experiences.mjs
.venv/bin/python scripts/verify_frontend_api.py
bash -n scripts/check.sh scripts/run.sh scripts/reset_demo.sh
git diff --check
