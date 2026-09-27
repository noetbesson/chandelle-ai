#!/usr/bin/env bash
# Fast everyday checks by default; --ask for voice/AI, --full before a PR.
set -euo pipefail
cd "$(dirname "$0")/.."
# Importing the ASGI app must not initialize or migrate the user's actual database.
check_runtime=$(mktemp -d "${TMPDIR:-/tmp}/chandelle-check.XXXXXX")
trap 'rm -rf -- "$check_runtime"' EXIT
export CHANDELLE_DB_PATH="$check_runtime/import.sqlite3"
export PYTHONDONTWRITEBYTECODE=1
export OPENAI_ENABLED=0
export GRADIUM_ENABLED=0
unset RUN_LIVE_OPENAI_SMOKE
case "${1:---quick}" in
  --quick)
    echo 'Vérification rapide · démarrage, catalogue, dialogue essentiel et frontend'
    python_tests=(backend/tests/test_local_launcher.py backend/tests/test_merged_runtime.py
      backend/tests/test_dialogue.py::test_no_cloud_without_consent_and_paid_turn_replays_exactly
      backend/tests/test_dialogue.py::test_provider_failure_is_visible_and_preserves_turn_for_retry
      backend/tests/test_dialogue.py::test_answer_uses_fresh_sources_and_a_second_model_call)
    ;;
  --ask)
    echo 'Vérification Ask · dialogue, OpenAI, Gradium et frontend'
    python_tests=(backend/tests/test_dialogue.py backend/tests/test_openai.py
      backend/tests/test_voice.py backend/tests/test_local_launcher.py backend/tests/test_merged_runtime.py
      backend/tests/test_ask_retrieval.py backend/tests/test_ai_discovery.py)
    ;;
  --full)
    echo 'Régression complète · à lancer avant une PR ou après un changement transversal'
    python_tests=()
    ;;
  --help|-h)
    echo 'Usage: bash scripts/check.sh [--quick | --ask | --full]'
    echo 'Sans argument: contrôles rapides. Tous les modes interdisent les appels API réels.'
    exit 0 ;;
  *) echo 'Option inconnue. Utiliser --quick, --ask ou --full.' >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then echo 'Une seule option attendue.' >&2; exit 2; fi
if [ "${1:---quick}" = --full ]; then
  .venv/bin/python scripts/test_offline.py
else
  .venv/bin/python scripts/test_offline.py "${python_tests[@]}"
fi
node --check frontend/app/app.mjs
node --check frontend/app/experiences.mjs
node --check frontend/app/voice.mjs
node --check frontend/app/discover.mjs
node --check frontend/app/chandelier.mjs
node --check frontend/app/icons.mjs
node --check frontend/app/visuals.mjs
node frontend/tests/test_discover.mjs
node frontend/tests/test_visuals.mjs
node frontend/tests/test_ui.mjs
node frontend/tests/test_experiences.mjs
node frontend/tests/test_voice.mjs
node frontend/tests/test_ai.mjs
node --check frontend/app/ai.mjs
node frontend/tests/test_share.mjs
node frontend/tests/test_calendar.mjs
node frontend/tests/test_date_deck.mjs
node frontend/tests/test_activity_cards.mjs
.venv/bin/python scripts/generate_date_contract.py --check
node frontend/node_modules/typescript/bin/tsc -p frontend/tsconfig.json --noEmit
node --check frontend/app/calendar.mjs

node frontend/tests/test_asset_cache.mjs
node --check frontend/app/share-page.mjs
node --check frontend/app/share-store.mjs
node --check frontend/app/pwa.mjs
node --check frontend/app/sw.js
.venv/bin/python scripts/verify_frontend_api.py
bash -n scripts/check.sh scripts/run.sh scripts/run_voice.sh scripts/reset_demo.sh
git diff --check
