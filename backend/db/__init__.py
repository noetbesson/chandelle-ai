"""SQLite and the common UTC/JSON persistence representation."""
from datetime import datetime, timezone
import json
from .database import Database


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
