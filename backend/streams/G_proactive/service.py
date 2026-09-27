"""Persistent proactive feed using the same B→C→E plan service."""
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4
from backend.db import now, encoded
from backend.streams.E_orchestrator.service import Query

class SuggestionService:
    def __init__(self,db,planning):self.db,self.planning=db,planning

    def check_opportunity(self,cid,calendar_read,demo=False,accelerated=False):
        """Real A → B → E → G path; the legacy mock demo check remains separate."""
        from backend.streams.A_calendar.service import instant
        from backend.streams.E_orchestrator.models import TimeWindow
        from .mood_tracker import MoodTracker, compute_opportunity_score
        from .notification_service import NotificationService
        current=datetime.now(timezone.utc)
        with self.db.connect() as c:
            members=c.execute('SELECT m.user_id,m.status,COALESCE(s.enabled,0) AS enabled FROM v2_memberships m LEFT JOIN v2_proactive_settings s ON s.user_id=m.user_id WHERE m.couple_id=?',(cid,)).fetchall()
            couple=c.execute('SELECT created_at FROM v2_couples WHERE id=?',(cid,)).fetchone()
            plans=c.execute("SELECT payload FROM v2_plans WHERE couple_id=? AND status IN ('accepted','completed')",(cid,)).fetchall()
        if len(members)!=2 or any(m['status']!='completed' or not m['enabled'] for m in members):
            return {'triggered':False,'reason':'Les deux personnes doivent activer les propositions dans Disponibilités.'}
        existing=next((x for x in self.list(cid)['items'] if x['state'] in ('new','viewed','snoozed')),None)
        if existing:
            if existing.get('source')=='calendar_proactive':
                NotificationService(self.db).send_date_proposal_notification(cid,existing['plan'],existing['id'],existing['opportunity_score'])
            return {'triggered':False,'reason':'Une proposition est déjà en attente.','suggestion_id':existing['id']}
        recent=next((x for x in self.list(cid)['items'] if x['state']=='dismissed' and instant(x['created_at'])>current-timedelta(days=1)),None)
        if recent:return {'triggered':False,'reason':'Pause de 24 heures après un refus.'}
        dates=[]
        for row in plans:
            p=json.loads(row['payload'])
            try:end=instant(p.get('end') or p['time_window']['end'])
            except (KeyError,ValueError,TypeError):continue
            if end>current:return {'triggered':False,'reason':'Une sortie confirmée est déjà prévue.'}
            dates.append(end)
        reference=max(dates) if dates else instant(couple['created_at'])
        days=(current-reference).total_seconds()/86400
        # Manual demo explicitly bypasses only age, never consent or availability.
        if demo:
            if accelerated and current-reference<timedelta(minutes=5):return {'triggered':False,'reason':'Mode accéléré : délai minimal de cinq minutes.'}
            days=7
        if days<7:return {'triggered':False,'reason':'La dernière sortie ou la création du couple date de moins de sept jours.'}
        slots=calendar_read.find_common_free_slots(members[0]['user_id'],members[1]['user_id'],current,current+timedelta(days=7),120)
        if not slots:return {'triggered':False,'reason':'Aucun créneau commun vérifié de deux heures dans les sept prochains jours.'}
        tracker=MoodTracker(self.db)
        moods=[tracker.get_recent_mood(m['user_id']) for m in members]
        # No event bonus without a documented current event.
        score=compute_opportunity_score(days,True,*moods,matching_upcoming_event=False)
        if score<.5:return {'triggered':False,'reason':'Le score ne justifie pas une proposition.','opportunity_score':score}
        result=None
        for slot in slots[:7]:
            try:
                result=self.planning.query(cid,Query(text='Une sortie à deux compatible avec nos goûts',activity_count=2,max_plans=1,time_window=TimeWindow(start=slot.start,end=slot.end)))
                break
            except ValueError:continue
        if not result or not result.get('plans'):return {'triggered':False,'reason':(result or {}).get('message') or 'Aucun programme compatible avec ces créneaux et vos contraintes.'}
        sid=uuid4().hex;created=now();plan=result['plans'][0]
        reasons=['Créneau commun vérifié ou saisi par les deux personnes.', 'Préférences autorisées prises en compte.']
        if demo:reasons.append('Test manuel : délai de sept jours ignoré.')
        item={'id':sid,'suggestion_id':sid,'couple_id':cid,'opportunity_score':score,'trigger_reasons':reasons,
              'plan':plan,'state':'new','created_at':created,'expires_at':slot.end.isoformat(),'evidence':reasons,
              'source':'calendar_proactive','mode':result['mode'],'run_id':result['run_id'],'triggered':True,
              'catalog_notice':'Programme sourcé sur le web ; disponibilité à confirmer.'}
        with self.db.connect() as c:c.execute('INSERT INTO v2_suggestions VALUES(?,?,?,?,?,?,NULL)',(sid,cid,'new',encoded(item),created,item['expires_at']))
        NotificationService(self.db).send_date_proposal_notification(cid,plan,sid,score)
        return item

    def list(self,cid):
        current=now()
        with self.db.connect() as c:
            c.execute("UPDATE v2_suggestions SET state='expired' WHERE couple_id=? AND expires_at<? AND state IN ('new','viewed','snoozed')",(cid,current))
            c.execute("UPDATE v2_suggestions SET state='new',snoozed_until=NULL WHERE couple_id=? AND state='snoozed' AND snoozed_until<=?",(cid,current))
            rows=c.execute('SELECT * FROM v2_suggestions WHERE couple_id=? ORDER BY created_at DESC',(cid,)).fetchall()
        items=[{**json.loads(r['payload']),'state':r['state'],'snoozed_until':r['snoozed_until']} for r in rows]
        return {'items':items,'total':len(items)}

    def check(self,cid,force=False):
        from backend.streams.A_calendar.calendar_read import CalendarRead
        calendar_read=CalendarRead(self.db)
        with self.db.connect() as c:
            opted=c.execute('SELECT 1 FROM v2_proactive_settings s JOIN v2_memberships m ON m.user_id=s.user_id WHERE m.couple_id=? AND s.enabled=1',(cid,)).fetchone()
        if opted or calendar_read.connected(cid):
            return self.check_opportunity(cid,calendar_read)
        feed=self.list(cid)['items']
        if not force:
            existing=next((x for x in feed if x['state'] in ('new','viewed','snoozed')),None)
            if existing:return existing
            recent=next((x for x in feed if x['state']=='dismissed' and datetime.fromisoformat(x['created_at'])>datetime.now(timezone.utc)-timedelta(days=1)),None)
            if recent:return {'triggered':False,'reason':'Dismissal cooldown until tomorrow','suggestion':recent}
        with self.db.connect() as c:
            last=c.execute("SELECT MAX(updated_at) FROM v2_plans WHERE couple_id=? AND status='completed'",(cid,)).fetchone()[0]
            saved=c.execute("SELECT COUNT(*) FROM v2_activity_states s JOIN v2_memberships m ON m.user_id=s.user_id WHERE m.couple_id=? AND s.state='saved'",(cid,)).fetchone()[0]
            changes=c.execute("SELECT COUNT(*) FROM v2_facts WHERE couple_id=? AND updated_at>? AND deleted=0 AND privacy_scope IN ('COUPLE_RECOMMENDATION','SHARED') AND consent_state='granted'",(cid,(datetime.now(timezone.utc)-timedelta(days=7)).isoformat())).fetchone()[0]
        days=(datetime.now(timezone.utc)-datetime.fromisoformat(last)).days if last else 30
        score=round(min(1,.25+min(days,30)/60+min(saved,5)*.03+min(changes,10)*.01),3)
        from backend.streams.A_calendar.service import AvailabilityService
        manual=bool(AvailabilityService(self.db)._rows(cid))
        reasons=[f'{days} days since the last completed date' if last else 'Your first date is waiting', 'A common manually entered slot is available' if manual else 'Un créneau de sortie sera proposé, à confirmer.']
        if saved:reasons.append('Saved activities can inspire this date')
        if changes:reasons.append('Recent preference updates informed candidate ranking')
        try:
            result=self.planning.query(cid,Query(text='A thoughtful date for us',activity_count=2,max_plans=1))
            if not result.get('plans'):return {'triggered':False,'reason':result.get('message') or 'Aucun programme compatible.'}
        except ValueError:
            return {'triggered':False,'reason':'Aucun programme compatible avec les disponibilités et contraintes actuelles.'}
        sid=uuid4().hex
        created=now();expires=(datetime.now(timezone.utc)+timedelta(days=7)).isoformat()
        item={'id':sid,'suggestion_id':sid,'couple_id':cid,'opportunity_score':score,'trigger_reasons':reasons,'plan':result['plans'][0],'state':'new','created_at':created,'expires_at':expires,'evidence':reasons,'source':'calendar_and_web_search','mode':result['mode'],'run_id':result['run_id'],'triggered':True}
        with self.db.connect() as c:c.execute('INSERT INTO v2_suggestions VALUES(?,?,?,?,?,?,NULL)',(sid,cid,'new',encoded(item),created,expires))
        return item

    def action(self,cid,sid,action,owner_id):
        item=next((x for x in self.list(cid)['items'] if x['id']==sid),None)
        if item is None:raise KeyError('Unknown suggestion')
        if action not in ('viewed','accepted','dismissed','snoozed','regenerate'):raise ValueError('Invalid suggestion action')
        if item['state'] in ('accepted','dismissed','expired') and action!=item['state'] and action!='regenerate':raise ValueError('Suggestion already resolved')
        if action==item['state']:return item
        if action=='accepted':self.planning.change(cid,item['plan']['id'],'accepted')
        until=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat() if action=='snoozed' else None
        state='dismissed' if action=='regenerate' else action
        with self.db.connect() as c:c.execute('UPDATE v2_suggestions SET state=?,snoozed_until=? WHERE id=?',(state,until,sid))
        if action=='dismissed':
            # Feedback remains an internal signal; never copy partner private facts.
            self.planning.memory.ingest(cid,'COUPLE',cid,owner_id,'pattern','suggestion-dismissed',{'count':sum(x['state']=='dismissed' for x in self.list(cid)['items'])},'SHARED','suggestion')
        return self.check(cid,True) if action=='regenerate' else {**item,'state':state,'snoozed_until':until}
