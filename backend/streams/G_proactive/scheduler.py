"""Optional process scheduler and durable per-couple leases. One web worker in this beta."""
from datetime import datetime, timedelta, timezone
import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from backend.db import now, encoded
from backend.integrations.calendar.store import LOCK

class ProactiveScheduler:
    def __init__(self,db,suggestions,calendar_read):
        self.db,self.suggestions,self.calendar_read=db,suggestions,calendar_read
        self.scheduler=None

    def start(self):
        if self.scheduler and self.scheduler.running:return
        if os.getenv('PROACTIVE_SCHEDULER_ENABLED')!='1':return
        self.scheduler=BackgroundScheduler(timezone='Europe/Paris',job_defaults={'max_instances':1,'coalesce':True,'misfire_grace_time':3600})
        if self.demo_mode():self.scheduler.add_job(self.run_all,'interval',minutes=5,id='dates')
        else:self.scheduler.add_job(self.run_all,'cron',hour=9,minute=0,id='dates')
        self.scheduler.start()

    def stop(self):
        if self.scheduler and self.scheduler.running:self.scheduler.shutdown(wait=False)
        self.scheduler=None

    @staticmethod
    def demo_mode():return os.getenv('CHANDELLE_DEV')=='1' and os.getenv('PROACTIVE_DEMO_MODE')=='1'

    def status(self,cid):
        job=self.scheduler.get_job('dates') if self.scheduler else None
        with self.db.connect() as c:r=c.execute('SELECT last_run,outcome FROM v2_proactive_runs WHERE couple_id=?',(cid,)).fetchone()
        import json
        return {'implemented':True,'running':bool(self.scheduler and self.scheduler.running),
                'cadence':'5 minutes (démo)' if self.demo_mode() else '09:00 Europe/Paris',
                'next_run':job.next_run_time.isoformat() if job and job.next_run_time else None,
                'last_run':r['last_run'] if r else None,'outcome':json.loads(r['outcome']) if r and r['outcome'] else None}

    def run(self,cid,demo=False,scheduled=False):
        if demo and os.getenv('CHANDELLE_DEV')!='1':raise PermissionError('Le test accéléré exige CHANDELLE_DEV=1.')
        with LOCK:
            current=datetime.now(timezone.utc)
            with self.db.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                row=c.execute('SELECT * FROM v2_proactive_runs WHERE couple_id=?',(cid,)).fetchone()
                if row and row['lease_until'] and row['lease_until']>now():return {'triggered':False,'reason':'Vérification déjà en cours.'}
                interval=timedelta(minutes=5) if self.demo_mode() else timedelta(hours=23)
                if scheduled and row and row['last_run'] and current-datetime.fromisoformat(row['last_run'])<interval:return {'triggered':False,'reason':'Déjà vérifié.'}
                c.execute('INSERT INTO v2_proactive_runs(couple_id,lease_until) VALUES(?,?) ON CONFLICT(couple_id) DO UPDATE SET lease_until=excluded.lease_until',(cid,(current+timedelta(minutes=10)).isoformat()))
            try:
                result=self.suggestions.check_opportunity(cid,self.calendar_read,demo=demo,accelerated=scheduled and self.demo_mode())
            except Exception:
                # No provider exception, tokens or raw mood in operational logs.
                result={'triggered':False,'reason':'Synchronisation ou génération indisponible. Aucune disponibilité supposée.'}
                logging.getLogger(__name__).warning('proactive_check failed')
            safe={k:v for k,v in result.items() if k in ('triggered','reason','opportunity_score','suggestion_id')}
            with self.db.connect() as c:c.execute('UPDATE v2_proactive_runs SET last_run=?,lease_until=NULL,outcome=? WHERE couple_id=?',(now(),encoded(safe),cid))
            return result

    def run_all(self):
        with self.db.connect() as c:
            cids=[r[0] for r in c.execute("SELECT m.couple_id FROM v2_memberships m JOIN v2_proactive_settings s ON s.user_id=m.user_id WHERE m.status='completed' AND s.enabled=1 GROUP BY m.couple_id HAVING COUNT(*)=2")]
        for cid in cids:
            demo=False
            if self.demo_mode():
                with self.db.connect() as c:r=c.execute('SELECT created_at FROM v2_couples WHERE id=?',(cid,)).fetchone()
                demo=bool(r and datetime.now(timezone.utc)-datetime.fromisoformat(r[0])>=timedelta(minutes=5))
            self.run(cid,demo=demo,scheduled=True)
