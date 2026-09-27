"""Refresh busy intervals; intersect only verified intervals or explicit manual availability."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
from backend.db import now
from backend.integrations.calendar.calendar_auth import CalendarAuth
from backend.integrations.calendar.store import CalendarStore, LOCK
from backend.integrations.calendar.provider import CalendarError, TimeSlot
from .time_slots import instant, intersect, merge_slots

UTC=timezone.utc
PARIS=ZoneInfo('Europe/Paris')

def subtract_busy(windows,busy):
    output=[]
    for start,end in windows:
        cursor=start
        for a,b in merge_slots(busy):
            if b<=cursor or a>=end:continue
            if a>cursor:output.append((cursor,min(a,end)))
            cursor=max(cursor,b)
        if cursor<end:output.append((cursor,end))
    return output

class CalendarRead:
    def __init__(self,db,provider_factory=None):
        self.db=db;self.store=CalendarStore(db)
        self.provider_factory=provider_factory or CalendarAuth(db).provider

    def connected(self,cid):
        with self.db.connect() as c:
            return bool(c.execute('SELECT 1 FROM v2_calendar_connections c JOIN v2_memberships m ON m.user_id=c.user_id WHERE m.couple_id=?',(cid,)).fetchone())

    def get_busy_slots(self,user_id,start,end):
        window=TimeSlot(start=start,end=end)
        if window.end-window.start>timedelta(days=14):raise CalendarError('calendar_range_limit')
        with LOCK:
            row=self.store.connection(user_id)
            try:
                slots=self.provider_factory(user_id).get_busy_slots(window.start,window.end)
                values=[s.model_dump(mode='json') for s in slots]
                with self.db.connect() as c:
                    changed=c.execute("UPDATE v2_calendar_connections SET busy=?,range_start=?,range_end=?,synced_at=?,status='connected',error=NULL WHERE user_id=? AND generation=?",
                        (self.store.seal(values),window.start.isoformat(),window.end.isoformat(),now(),user_id,row['generation'])).rowcount
                if not changed:raise CalendarError('calendar_disconnected')
                return slots
            except Exception:
                with self.db.connect() as c:
                    c.execute("UPDATE v2_calendar_connections SET status='error',error='calendar_sync_failed' WHERE user_id=? AND generation=?",(user_id,row['generation']))
                raise CalendarError('calendar_sync_failed') from None

    def refresh(self,user_id):
        start=datetime.now(UTC)
        self.get_busy_slots(user_id,start,start+timedelta(days=7))
        return self.store.status(user_id)

    def free(self,uid,start,end):
        with self.db.connect() as c:
            row=c.execute('SELECT * FROM v2_calendar_connections WHERE user_id=?',(uid,)).fetchone()
            manual=c.execute('SELECT payload FROM v2_availability WHERE user_id=?',(uid,)).fetchone()
        if manual:
            windows=intersect([(instant(s['start']),instant(s['end'])) for s in json.loads(manual[0])],[(start,end)],1)
        else:
            windows=[]
            for offset in range((end.astimezone(PARIS).date()-start.astimezone(PARIS).date()).days+1):
                day=(start.astimezone(PARIS)+timedelta(days=offset)).replace(hour=18,minute=0,second=0,microsecond=0)
                a,b=max(start,day.astimezone(UTC)),min(end,day.replace(hour=23).astimezone(UTC))
                if b>a:windows.append((a,b))
        if row is None:
            return windows if manual else []  # Disconnected partner != free calendar.
        if row['status']!='connected' or not row['synced_at'] or not row['busy']:return []
        if datetime.now(UTC)-instant(row['synced_at'])>timedelta(minutes=15):return []
        windows=intersect(windows,[(instant(row['range_start']),instant(row['range_end']))],1)
        try: busy=[(instant(s['start']),instant(s['end'])) for s in self.store.open(row['busy'])]
        except CalendarError:return []
        return subtract_busy(windows,busy)

    def cached_common(self,cid,start=None,end=None,minimum=30):
        start=start or datetime.now(UTC);end=end or start+timedelta(days=7)
        with self.db.connect() as c:uids=[r[0] for r in c.execute('SELECT user_id FROM v2_memberships WHERE couple_id=?',(cid,))]
        if len(uids)!=2:return []
        return intersect(self.free(uids[0],start,end),self.free(uids[1],start,end),minimum)

    def find_common_free_slots(self,user_a_id,user_b_id,start,end,min_duration_minutes=60):
        if not 1<=min_duration_minutes<=1440:raise ValueError('Durée minimale invalide.')
        window=TimeSlot(start=start,end=end)
        if window.end-window.start>timedelta(days=14):raise CalendarError('calendar_range_limit')
        with self.db.connect() as c:
            same=c.execute('SELECT a.couple_id FROM v2_memberships a JOIN v2_memberships b ON b.couple_id=a.couple_id WHERE a.user_id=? AND b.user_id=?',(user_a_id,user_b_id)).fetchone()
        if user_a_id==user_b_id or not same:raise PermissionError('Deux membres du même couple sont requis.')
        for uid in (user_a_id,user_b_id):
            with self.db.connect() as c:connected=c.execute('SELECT 1 FROM v2_calendar_connections WHERE user_id=?',(uid,)).fetchone()
            if connected:self.get_busy_slots(uid,start,end)
        return [TimeSlot(start=a,end=b) for a,b in intersect(self.free(user_a_id,start,end),self.free(user_b_id,start,end),min_duration_minutes)]
