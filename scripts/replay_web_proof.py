"""Replay captured LIVE provider facts through corrected filters, no external calls."""
import os,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['OPENAI_ENABLED']='0';os.environ['PROACTIVE_SCHEDULER_ENABLED']='0'
from backend.api.app import create_app
from backend.integrations.openai import OpenAIAdapter,ParsedRequest
from backend.streams.E_orchestrator.service import Query
app=create_app(ROOT/'.runtime/web-live-validation.sqlite3');state=app.state.v2
with state['db'].connect() as c:
    record=c.execute('SELECT couple_id,payload FROM v2_runs ORDER BY created_at DESC LIMIT 1').fetchone()
    raw=c.execute('SELECT payload FROM v2_web_cache ORDER BY created_at DESC LIMIT 1').fetchone()
cid=record[0];previous=json.loads(record[1]);web=json.loads(raw[0]);owner=previous['_owner_id']
def parse(self,text):
    self.last_mode='openai';self.last_fallback=None
    return ParsedRequest(categories=previous['trace'][1]['categories'])
OpenAIAdapter.parse=parse
state['planning'].web=type('CapturedWeb',(),{'search':lambda self,member,body:{**web,'cached':True}})()
result=state['planning'].query(cid,Query(activity_count=previous.get('requested_steps',2),text='Un restaurant japonais puis une balade gratuite à Paris',time_window=previous['_activity_search']['time_window']),deck_options={'owner_id':owner,'duration':360,'travel':30})
result.update(search_id=result['run_id'],proposals=result['plans'])
(ROOT/'.runtime/web-live-replayed.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'cards':len(result['activities']),'plans':len(result['plans']),'trace':result['trace']},ensure_ascii=True))
