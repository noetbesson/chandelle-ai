"""Only a plan approved by both people can write; retries retain per-member results."""
import hashlib
import json
import os
from backend.db import now
from backend.integrations.calendar.provider import CalendarEvent, CalendarError
from backend.integrations.calendar.calendar_auth import CalendarAuth
from backend.integrations.calendar.store import CalendarStore, LOCK
from backend.streams.F_booking.service import schedule

class CalendarWrite:
    def __init__(self,db,planning,provider_factory=None):
        self.db,self.planning=db,planning;self.store=CalendarStore(db)
        self.provider_factory=provider_factory or CalendarAuth(db).provider

    def preview(self,cid,pid):
        plan=self.planning.get(cid,pid)
        entries=list(schedule(plan))
        if not entries:raise ValueError('Programme vide.')
        demo=any(a.get('demo',True) for a in plan['activities'])
        itinerary=' ; '.join(a.get('title',a.get('name','Activité'))+' '+a['start']+'-'+a['end'] for a in plan['activities'])
        event=CalendarEvent(title=('DÉMO : ' if demo else '')+'Sortie Chandelle',start=entries[0][1],end=entries[-1][2],
            location=' / '.join(a.get('address','') for a in plan['activities'])[:500],
            description=('Programme confirmé à deux. Aucune réservation effectuée. '+('Activités fictives de démonstration. ' if demo else 'Vérifiez la disponibilité des lieux. ')+itinerary)[:2000])
        with self.db.connect() as c:
            rows=[dict(r) for r in c.execute('SELECT m.user_id,c.generation FROM v2_memberships m LEFT JOIN v2_calendar_connections c ON c.user_id=m.user_id WHERE m.couple_id=? ORDER BY m.user_id',(cid,))]
        revision=hashlib.sha256(json.dumps([event.model_dump(mode='json'),rows,plan['status'],plan['activities'],plan.get('total_couple_cost')],sort_keys=True).encode()).hexdigest()
        return plan,event,revision,rows,demo

    def status(self,member,pid):
        plan,event,rev,rows,demo=self.preview(member['couple_id'],pid)
        with self.db.connect() as c:
            approvals=[r[0] for r in c.execute('SELECT user_id FROM v2_calendar_approvals WHERE plan_id=? AND revision=?',(pid,rev))]
            own=c.execute('SELECT status,error,revision FROM v2_calendar_events WHERE plan_id=? AND user_id=?',(pid,member['id'])).fetchone()
        return {'plan_id':pid,'revision':rev,'event':event.model_dump(mode='json'),'demo':demo,
                'approved_by_me':member['id'] in approvals,'approvals':len(approvals),'required':2,
                'own_event':{'status':own['status'] if own['revision']==rev else 'confirmation_required','error':own['error']} if own else None,'connected_calendars':sum(bool(r['generation']) for r in rows),
                'operation':'delete' if plan['status']=='cancelled' else 'upsert'}

    def confirm(self,member,pid,revision):
        with LOCK:
            plan,event,rev,rows,demo=self.preview(member['couple_id'],pid)
            if revision!=rev:raise ValueError('Le programme a changé. Relisez puis confirmez à nouveau.')
            if plan['status'] not in ('accepted','cancelled'):raise ValueError('Acceptez le programme avant la confirmation calendrier.')
            if demo and plan['status']!='cancelled' and not (os.getenv('CHANDELLE_DEV')=='1' and os.getenv('CALENDAR_ALLOW_DEMO_EVENTS')=='1'):
                raise ValueError('Écriture des activités fictives désactivée. Utilisez un calendrier de test et le mode démo explicite.')
            operation='delete' if plan['status']=='cancelled' else 'upsert'
            with self.db.connect() as c:
                c.execute('INSERT INTO v2_calendar_approvals VALUES(?,?,?,?,?) ON CONFLICT(plan_id,user_id) DO UPDATE SET revision=excluded.revision,operation=excluded.operation,created_at=excluded.created_at',(pid,member['id'],rev,operation,now()))
                count=c.execute('SELECT COUNT(*) FROM v2_calendar_approvals WHERE plan_id=? AND revision=? AND operation=?',(pid,rev,operation)).fetchone()[0]
            if count!=2:return self.status(member,pid)
            for row in rows:
                uid=row['user_id']
                if not row['generation']:continue
                with self.db.connect() as c:old=c.execute('SELECT * FROM v2_calendar_events WHERE plan_id=? AND user_id=?',(pid,uid)).fetchone()
                if old and old['revision']==rev and old['status'] in ('synced','deleted'):continue
                eid=old['event_id'] if old and old['generation']==row['generation'] else None
                try:
                    provider=self.provider_factory(uid)
                    if operation=='delete':
                        if eid and not provider.delete_event(eid):raise CalendarError('calendar_delete_failed')
                        status='deleted'
                    else:
                        if eid:
                            if not provider.update_event(eid,event):raise CalendarError('calendar_update_failed')
                        else:eid=provider.create_event(event,':'.join([pid,uid,row['generation']]))
                        status='synced'
                    error=None
                except Exception:status,error='failed','calendar_write_failed'
                with self.db.connect() as c:
                    c.execute('INSERT INTO v2_calendar_events VALUES(?,?,?,?,?,?,?) ON CONFLICT(plan_id,user_id) DO UPDATE SET generation=excluded.generation,event_id=excluded.event_id,revision=excluded.revision,status=excluded.status,error=excluded.error',(pid,uid,row['generation'],eid,rev,status,error))
                    c.execute('UPDATE v2_calendar_connections SET busy=NULL,synced_at=NULL WHERE user_id=? AND generation=?',(uid,row['generation']))
            return self.status(member,pid)
