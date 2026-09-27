#!/usr/bin/env bash
# Keep the API key out of command history and browser code.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -z "${GRADIUM_API_KEY:-}" ]]; then
  read -r -s -p "Clé API Gradium (saisie masquée) : " GRADIUM_API_KEY
  echo
fi
if [[ -z "${GRADIUM_VOICE_ID:-}" ]]; then
  read -r -p "Identifiant de voix française Gradium : " GRADIUM_VOICE_ID
fi
if [[ -z "$GRADIUM_API_KEY" || -z "$GRADIUM_VOICE_ID" ]]; then
  echo "La clé et l'identifiant de voix sont requis." >&2
  exit 1
fi
export GRADIUM_API_KEY GRADIUM_VOICE_ID
export GRADIUM_ENABLED=1
exec bash scripts/run.sh
