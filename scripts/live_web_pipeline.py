"""Explicit, bounded LIVE proof; never part of offline tests. No private user prompt."""
import os,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
if os.getenv('RUN_LIVE_WEB_PIPELINE')!='1':raise SystemExit('Set RUN_LIVE_WEB_PIPELINE=1 explicitly.')
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
from backend.db import Database
from backend.integrations.openai import OpenAIAdapter
from backend.integrations.ai_budget import AIBudget
# Same persistent spend ledger as the application, even though profiles/results are isolated.
ledger=Database(ROOT/'.runtime/chandelle_v2.sqlite3')
OpenAIAdapter._reserve=lambda self,kind,model:AIBudget(ledger).reserve(kind,model)
def finish(self,ticket,outcome,response=None):
    if ticket:
        usage=getattr(response,'usage',None)
        AIBudget(ledger).finish(ticket,outcome,usage.model_dump() if hasattr(usage,'model_dump') else {})
OpenAIAdapter._finish=finish
from backend.api.app import create_app
from fastapi.testclient import TestClient
from backend.tests.test_api import ready,headers
app=create_app(ROOT/'.runtime/web-live-validation.sqlite3')
client=TestClient(app)
_,a,_=ready(client)
response=client.post('/api/v2/dates/search',headers=headers(a),json={'constraints':{'text':'Un restaurant japonais puis une balade gratuite à Paris pour demain soir. Des adresses nommées avec leurs sources.','mode':'auto','activity_count':2}})
data=response.json()
(ROOT/'.runtime/web-live-result.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'http':response.status_code,'status':data.get('status'),'cards':len(data.get('activities',[])),'plans':len(data.get('proposals',[])),'reason':data.get('empty_reason'),'trace':data.get('trace')},ensure_ascii=True))
if response.status_code!=200 or data.get('status')!='completed' or not data.get('activities'):raise SystemExit(1)
