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
node frontend/tests/test_ai.mjs
node --check frontend/app/ai.mjs
node frontend/tests/test_ui.mjs
node frontend/tests/test_experiences.mjs
node frontend/tests/test_share.mjs
node --check frontend/app/share-page.mjs
node --check frontend/app/share-store.mjs
node --check frontend/app/pwa.mjs
node --check frontend/app/sw.js
.venv/bin/python scripts/verify_frontend_api.py
bash -n scripts/check.sh scripts/run.sh scripts/reset_demo.sh
git diff --check
