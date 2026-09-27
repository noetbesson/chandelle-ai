"""V2 calendar adapter inspired by the peer time.ts; A's contract stays intact."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, SecretStr, model_validator
from backend.integrations.google_calendar import busy_intervals, google_ical_url

from backend.streams.E_orchestrator.models import TimeWindow

PARIS = ZoneInfo('Europe/Paris')
UTC = timezone.utc


def default_availability(now: datetime | None = None) -> TimeWindow:
    """Mock A availability: next Friday 19:00–23:15, Europe/Paris."""
    current = now or datetime.now(ZoneInfo("Europe/Paris"))
    if current.tzinfo is None:
        current = current.replace(tzinfo=ZoneInfo("Europe/Paris"))
    days = (4 - current.weekday()) % 7
    start = current.replace(hour=19, minute=0, second=0, microsecond=0) + timedelta(days=days)
    if start <= current:
        start += timedelta(days=7)
    return TimeWindow(start=start, end=start.replace(hour=23, minute=15))



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


def paris_window(window):
    start, end = instant(window.start), instant(window.end)
    if end <= start or end - start > timedelta(days=2):
        raise ValueError('Le créneau doit durer entre une minute et deux jours.')
    # Fixed offsets avoid datetime's wall-clock subtraction at DST transitions.
    local = lambda dt: datetime.fromisoformat(dt.astimezone(PARIS).isoformat())
    return TimeWindow(start=local(start), end=local(end))


class AvailabilityInput(BaseModel):
    slots: list[TimeWindow] = Field(default_factory=list, max_length=500)

    @model_validator(mode='after')
    def validate_slots(self):
        for slot in self.slots:
            paris_window(slot)
        return self


class GoogleCalendarInput(BaseModel):
    url: SecretStr = Field(repr=False)
    start_date: date
    days: int = Field(default=14, ge=1, le=31)
    daily_start: time = time(8)
    daily_end: time = time(23)

    @model_validator(mode='after')
    def validate_import(self):
        google_ical_url(self.url.get_secret_value())
        if self.daily_start.tzinfo or self.daily_end.tzinfo or self.daily_start >= self.daily_end:
            raise ValueError('Choisissez une plage quotidienne croissante, en heures de Paris.')
        return self


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


class AvailabilityService:
    def __init__(self, db):
        self.db = db

    def save(self, cid, uid, body, imported=None):
        from backend.db import encoded, now
        slots = merge_slots([(instant(s.start), instant(s.end)) for s in body.slots])
        with self.db.connect() as con:
            con.execute('INSERT INTO v2_availability VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at',
                        (uid, cid, encoded([{'start':a.isoformat(), 'end':b.isoformat()} for a,b in slots]), now()))
            con.execute('DELETE FROM v2_calendar_imports WHERE user_id=?', (uid,))
            if imported:
                con.execute('INSERT INTO v2_calendar_imports(user_id,couple_id,imported_at,start_date,days,daily_start,daily_end) VALUES(?,?,?,?,?,?,?)',
                    (uid,cid,now(),str(imported.start_date),imported.days,str(imported.daily_start),str(imported.daily_end)))
            con.execute("UPDATE v2_suggestions SET state='expired' WHERE couple_id=? AND state IN ('new','viewed','snoozed')",(cid,))
        return self.state(cid, uid)

    def import_calendar(self, cid, uid, body, data):
        windows = [(instant(datetime.combine(body.start_date + timedelta(days=i), body.daily_start)),
                    instant(datetime.combine(body.start_date + timedelta(days=i), body.daily_end))) for i in range(body.days)]
        busy = merge_slots(busy_intervals(data, windows[0][0], windows[-1][1]))
        free = []
        for start, end in windows:
            cursor = start
            for a, b in busy:
                if b <= cursor or a >= end:
                    continue
                if a > cursor:
                    free.append((cursor, min(a, end)))
                cursor = max(cursor, min(b, end))
            if cursor < end:
                free.append((cursor, end))
        slots = [TimeWindow(start=a, end=b) for a,b in free if b-a >= timedelta(minutes=30)]
        result = self.save(cid, uid, AvailabilityInput(slots=slots), imported=body)
        return {**result, 'imported_slots':len(slots)}

    def _rows(self, cid):
        import json
        with self.db.connect() as con:
            return {r['user_id']: json.loads(r['payload']) for r in con.execute('SELECT * FROM v2_availability WHERE couple_id=?', (cid,))}

    def state(self, cid, uid):
        rows = self._rows(cid)
        common = self.common(cid)
        with self.db.connect() as con:
            source = con.execute('SELECT imported_at,start_date,days,daily_start,daily_end FROM v2_calendar_imports WHERE user_id=? AND couple_id=?', (uid,cid)).fetchone()
        return {'calendar_import':dict(source) if source else None, 'own_slots':rows.get(uid, []), 'configured':uid in rows,
                'mode':'manual' if rows else 'demo', 'timezone':'Europe/Paris',
                'common_slots':[{'start':a.isoformat(), 'end':b.isoformat()} for a,b in common],
                'both_configured':len(rows)==2}

    def common(self, cid):
        rows = self._rows(cid)
        if not rows:
            slot = default_availability()
            return [(instant(slot.start), instant(slot.end))]
        if len(rows) != 2:
            return []
        slots = [[(instant(s['start']), instant(s['end'])) for s in values] for values in rows.values()]
        return intersect(*slots)

    def windows(self, cid, requested=None):
        rows = self._rows(cid)
        if requested is not None and not rows:
            return [paris_window(requested)]
        common = self.common(cid)
        if requested is not None:
            common = intersect(common, [(instant(requested.start), instant(requested.end))])
        else:
            current = datetime.now(UTC)
            common = [(max(a,current),b) for a,b in common if b-max(a,current)>=timedelta(minutes=30)]
        if not common:
            raise ValueError('Aucun créneau commun. Renseignez les disponibilités des deux personnes.')
        return [paris_window(TimeWindow(start=a,end=b)) for a,b in common]
