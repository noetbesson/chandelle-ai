"""Existing A interval operations, shared without service import cycles."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
PARIS=ZoneInfo("Europe/Paris")
UTC=timezone.utc

def instant(value):
    """Interpret legacy naive values as Paris; reject ambiguous/nonexistent times."""
    dt = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
    if dt.tzinfo is not None:
        return dt.astimezone(UTC)
    options = {dt.replace(tzinfo=PARIS, fold=fold).astimezone(UTC) for fold in (0, 1)
               if dt.replace(tzinfo=PARIS, fold=fold).astimezone(UTC).astimezone(PARIS).replace(tzinfo=None) == dt}
    if len(options) != 1:
        raise ValueError('Heure de Paris inexistante ou ambiguë : indiquez un décalage UTC explicite.')
    return options.pop()


def merge_slots(slots):
    merged = []
    for start, end in sorted(slots):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def intersect(left, right, minimum=30):
    left, right = merge_slots(left), merge_slots(right)
    matches = merge_slots([(max(a, c), min(b, d)) for a, b in left for c, d in right if max(a, c) < min(b, d)])
    return [(a, b) for a, b in matches if b-a >= timedelta(minutes=minimum)]


