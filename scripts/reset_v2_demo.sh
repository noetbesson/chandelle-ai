#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" != "--confirm-reset-local-v2" ]]; then
  echo 'Usage: scripts/reset_v2_demo.sh --confirm-reset-local-v2 (stop the local server first)'
  exit 1
fi
.venv/bin/python - <<'PY'
from pathlib import Path
runtime=Path('.runtime')
for name in ('chandelle_v2.sqlite3','chandelle_v2.sqlite3-wal','chandelle_v2.sqlite3-shm','demo-session.json'):
    (runtime/name).unlink(missing_ok=True)
uploads=runtime/'uploads'
if uploads.exists():
    for path in uploads.iterdir():
        if path.is_file() and len(path.stem)==32 and all(c in '0123456789abcdef' for c in path.stem):
            path.unlink()
print('Local V2 database/uploads reset; V1 memory preserved.')
PY
