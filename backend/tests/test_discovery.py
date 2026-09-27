"""Discovery now ranks only explicit web batches and revalidates saved pools."""
import json
from datetime import datetime,timedelta,timezone
import pytest
from backend.tests.test_api import client,offline_only,ready,headers,query
from backend.streams.C_discovery.service import department_code,record_web
from backend.tests.test_web_pipeline import fact
from backend.streams.E_orchestrator.models import TimeWindow

@pytest.mark.parametrize('label,address,code',[('Paris','','75'),('Hauts-de-Seine','','92'),(None,'75009 Paris','75'),('Rhône','69001 Lyon',None)])
def test_department_normalization(label,address,code):assert department_code(label,address)==code

def test_no_default_repository_or_catalogue(client):
    from backend.streams.C_discovery import LocalActivityRepository
    from backend.streams.E_orchestrator.repository import load_candidates
    assert LocalActivityRepository().list_activities()==[] and load_candidates()==[]
    _,a,_=ready(client)
    assert client.get('/api/v2/activities',headers=headers(a)).json()['total']==0
    assert client.app.state.v2['catalog'].discover(a['id'],None)==[]

def test_person_b_refusal_and_radius_are_traced_without_private_notes(client):
    couple,a,b=ready(client);state=client.app.state.v2
    records=[record_web(fact(),datetime.now(timezone.utc).isoformat())]
    memory=state['memory'];memory.ingest(couple['couple_id'],'PERSON',b['id'],b['id'],'dislikes','refusal',{'values':['food']},'COUPLE_RECOMMENDATION','conversation')
    trace=[];rows,_=state['catalog'].filter_web(couple['couple_id'],records,trace=trace)
    assert rows==[] and next(t for t in trace if t['stage']=='explicit_exclusions')['removed']==1
    assert 'refusal' not in json.dumps(trace) and b['id'] not in json.dumps(trace)

def test_recommendation_changes_only_after_authorized_memory(client):
    couple,a,b=ready(client);state=client.app.state.v2
    initial=query(client,a);window={'start':'2026-09-26T18:00:00+02:00','end':'2026-09-26T23:00:00+02:00'}
    ids={r['id'] for r in initial['activities']}
    def scores():return {r['activity']['id']:r['couple_score'] for r in state['catalog'].discover(couple['couple_id'],window,candidate_ids=ids,limit=100)}
    before=scores()
    f=state['memory'].ingest(couple['couple_id'],'PERSON',b['id'],b['id'],'interests','private-jazz',{'values':['jazz']},'PRIVATE','conversation')
    assert scores()==before
    state['memory'].ingest(couple['couple_id'],'PERSON',a['id'],a['id'],'interests','shared-jazz',{'values':['jazz']},'COUPLE_RECOMMENDATION','conversation')
    assert scores()!=before

def test_explicit_unknown_accessibility_is_not_claimed(client):
    couple,a,_=ready(client);state=client.app.state.v2
    state['memory'].ingest(couple['couple_id'],'PERSON',a['id'],a['id'],'constraints','access',{'accessibility':['wheelchair']},'COUPLE_RECOMMENDATION','conversation')
    rows,_=state['catalog'].filter_web(couple['couple_id'],[record_web(fact(),datetime.now(timezone.utc).isoformat())])
    assert rows==[]
