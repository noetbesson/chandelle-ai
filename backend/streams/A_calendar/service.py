"""V2 calendar adapter inspired by the peer time.ts; A's contract stays intact."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, model_validator

from backend.streams.E_orchestrator.models import TimeWindow

PARIS = ZoneInfo('Europe/Paris')
UTC = timezone.utc
from .time_slots import instant, intersect, merge_slots


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



def paris_window(window):
    start, end = instant(window.start), instant(window.end)
    if end <= start or end - start > timedelta(days=2):
        raise ValueError('Le créneau doit durer entre une minute et deux jours.')
    # Fixed offsets avoid datetime's wall-clock subtraction at DST transitions.
    local = lambda dt: datetime.fromisoformat(dt.astimezone(PARIS).isoformat())
    return TimeWindow(start=local(start), end=local(end))


class AvailabilityInput(BaseModel):
    slots: list[TimeWindow] = Field(default_factory=list, max_length=50)

    @model_validator(mode='after')
    def validate_slots(self):
        for slot in self.slots:
            paris_window(slot)
        return self


class AvailabilityService:
    def __init__(self, db):
        self.db = db

    def save(self, cid, uid, body):
        from backend.db import encoded, now
        slots = merge_slots([(instant(s.start), instant(s.end)) for s in body.slots])
        with self.db.connect() as con:
            con.execute('INSERT INTO v2_availability VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at',
                        (uid, cid, encoded([{'start':a.isoformat(), 'end':b.isoformat()} for a,b in slots]), now()))
            con.execute("UPDATE v2_suggestions SET state='expired' WHERE couple_id=? AND state IN ('new','viewed','snoozed')",(cid,))
        return self.state(cid, uid)

    def _rows(self, cid):
        import json
        with self.db.connect() as con:
            return {r['user_id']: json.loads(r['payload']) for r in con.execute('SELECT * FROM v2_availability WHERE couple_id=?', (cid,))}

    def state(self, cid, uid):
        from .calendar_read import CalendarRead
        rows = self._rows(cid)
        common = self.common(cid)
        return {'own_slots':rows.get(uid, []), 'configured':uid in rows,
                'mode':'connected' if CalendarRead(self.db).connected(cid) else 'manual' if rows else 'demo', 'timezone':'Europe/Paris',
                'common_slots':[{'start':a.isoformat(), 'end':b.isoformat()} for a,b in common],
                'both_configured':len(rows)==2}

    def common(self, cid):
        from .calendar_read import CalendarRead
        calendars = CalendarRead(self.db)
        if calendars.connected(cid):
            return calendars.cached_common(cid)
        rows = self._rows(cid)
        if not rows:
            slot = default_availability()
            return [(instant(slot.start), instant(slot.end))]
        if len(rows) != 2:
            return []
        slots = [[(instant(s['start']), instant(s['end'])) for s in values] for values in rows.values()]
        return intersect(*slots)

    def windows(self, cid, requested=None):
        from .calendar_read import CalendarRead
        rows = self._rows(cid)
        if requested is not None and not rows and not CalendarRead(self.db).connected(cid):
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
