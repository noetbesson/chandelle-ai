"""Persistent proactive feed using the same B→C→E plan service."""
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4
from backend.domain.onboarding import now, encoded
from backend.domain.planning import Query

class SuggestionService:
    def __init__(self,db,planning):self.db,self.planning=db,planning

    def list(self,cid):
        current=now()
        with self.db.connect() as c:
            c.execute("UPDATE v2_suggestions SET state='expired' WHERE couple_id=? AND expires_at<? AND state IN ('new','viewed','snoozed')",(cid,current))
            c.execute("UPDATE v2_suggestions SET state='new',snoozed_until=NULL WHERE couple_id=? AND state='snoozed' AND snoozed_until<=?",(cid,current))
            rows=c.execute('SELECT * FROM v2_suggestions WHERE couple_id=? ORDER BY created_at DESC',(cid,)).fetchall()
        items=[{**json.loads(r['payload']),'state':r['state'],'snoozed_until':r['snoozed_until']} for r in rows]
        return {'items':items,'total':len(items)}

    def check(self,cid,force=False):
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
        reasons=[f'{days} days since the last completed date' if last else 'Your first date is waiting', 'A common mock calendar slot is available']
        if saved:reasons.append('Saved activities can inspire this date')
        if changes:reasons.append('Recent preference updates informed candidate ranking')
        result=self.planning.query(cid,Query(text='A thoughtful date for us',max_plans=1))
        sid=uuid4().hex
        created=now();expires=(datetime.now(timezone.utc)+timedelta(days=7)).isoformat()
        item={'id':sid,'suggestion_id':sid,'couple_id':cid,'opportunity_score':score,'trigger_reasons':reasons,'plan':result['plans'][0],'state':'new','created_at':created,'expires_at':expires,'evidence':reasons,'source':'mock_calendar_and_internal_catalog','mode':result['mode'],'run_id':result['run_id'],'triggered':True}
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
