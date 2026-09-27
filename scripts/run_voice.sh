#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Configuration is data; secrets never become shell commands or arguments.
exec .venv/bin/python scripts/run_local.py --voice "$@"
