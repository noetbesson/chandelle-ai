"""Actual local API and SQLite; synthetic catalogue, no external API calls."""
from datetime import datetime, timedelta
from dataclasses import replace
import json
import math
import pytest
from backend.tests.test_api import client,offline_only,ready,headers
from backend.streams.E_orchestrator.date_composer import (
    generate_candidate_combos,select_diverse_top_3,weighted_score,SCORE_WEIGHTS,
)
from backend.streams.E_orchestrator.models import CandidateActivity
from backend.streams.E_orchestrator.planner import Slot


def slot(aid,offset=0,kind='food',price=20,score=.8,lat=48.8566):
    start=datetime(2026,9,26,18)+timedelta(minutes=offset)
    end=start+timedelta(minutes=45)
    activity=CandidateActivity(id=aid,type=kind,name=aid,start=start.strftime('%H:%M'),end=end.strftime('%H:%M'),
        price_per_person=price,location={'lat':lat,'lng':2.3522},match_score=score,tags=['quiet'])
    return Slot(activity,start,end,score,score,score)


def search(client,member,**constraints):
    return client.post('/api/dates/search',headers=headers(member),json={'constraints':{
        'text':'Une sortie à deux','activity_count':2,'budget':150,
        'time_window':{'start':'2026-09-26T18:00:00','end':'2026-09-26T23:45:00'},**constraints}})


def test_pure_score_and_exact_temporal_combinations():
    assert sum(SCORE_WEIGHTS.values())==pytest.approx(1)
    assert weighted_score({k:1 for k in SCORE_WEIGHTS})==1
    with pytest.raises(ValueError):weighted_score({k:math.nan for k in SCORE_WEIGHTS})
    a,b=slot('a'),slot('b',60,'culture')
    assert len(generate_candidate_combos([b,a],2,120,budget=100))==1
    assert not generate_candidate_combos([a,b],3,120,budget=100)
    assert not generate_candidate_combos([a,b],2,120,budget=70)
    assert not generate_candidate_combos([a,b],2,90,budget=100)
    assert not generate_candidate_combos([a,slot('far',60,lat=49.0)],2,200,budget=100)
    assert not generate_candidate_combos([a,slot('overlap',30)],2,200,budget=100)
    assert not generate_candidate_combos([a,b],2,120,max_travel_time_minutes=0,budget=100)


def test_diversification_and_truthful_scarcity():
    options=[slot('a',kind='food',price=30),slot('b',kind='food',price=31,score=.79),
             slot('c',kind='culture',price=10,score=.77),slot('d',kind='outdoors',price=0,score=.76)]
    combos=generate_candidate_combos(options,1,90)
    selected=select_diverse_top_3(combos)
    assert selected[0].ids==('a',)
    assert {x.ids for x in selected}=={('a',),('c',),('d',)}
    assert len(select_diverse_top_3(combos[:1]*3))==1


def test_search_three_persisted_proposals_auth_and_scoring(client):
    couple,a,b=ready(client)
    assert client.post('/api/dates/search',json={}).status_code==403
    assert client.post('/api/dates/search',headers=headers(a),json={'couple_id':'foreign'}).status_code==403
    assert search(client,a,mode='openai').status_code==200
    response=search(client,a);assert response.status_code==200,response.text
    data=response.json();plans=data['proposals']
    assert len(plans)==3 and len({tuple(x['id'] for x in p['activities']) for p in plans})==3
    assert data['composition']['combos_generated']>=3
    assert all(len(p['activities'])==2 and p['estimated_total_eur']<=150 for p in plans)
    assert all(not any(k.startswith('_') for k in p) for p in plans)
    assert 'PRIVATE_ONBOARDING_SENTINEL' not in response.text
    for p in plans:
        saved=client.get('/api/v2/date-plans/'+p['id'],headers=headers(a)).json()
        assert saved['activities']==p['activities'] and saved['search_id']==data['search_id']
    no=search(client,a,budget=0,categories=['food']).json()
    assert no['proposals']==[] and no['warnings']
    assert client.post('/api/v2/dates/search',headers=headers(b),json={'constraints':{'activity_count':1}}).status_code==200


def test_replace_keeps_complete_other_activity_and_other_plans(client):
    _,a,_=ready(client)
    result=search(client,a).json();plan=result['proposals'][0];target=plan['activities'][0]['id']
    route=f"/api/dates/{plan['id']}/replace-activity"
    failed=client.post(route,headers=headers(a),json={'activity_id_to_replace':target,'new_constraints':'foobar incantation'})
    assert failed.status_code==422
    response=client.post(route,headers=headers(a),json={'activity_id_to_replace':target,'new_constraints':'moins de 40 €'})
    assert response.status_code==200,response.text
    changed=response.json();assert changed['id']==plan['id']
    assert changed['activities'][1]==plan['activities'][1]
    assert changed['activities'][0]['id']!=target and changed['activities'][0]['price_per_person']<=40
    for other in result['proposals'][1:]:
        assert client.get('/api/v2/date-plans/'+other['id'],headers=headers(a)).json()['activities']==other['activities']
    client.patch('/api/v2/date-plans/'+plan['id'],headers=headers(a),json={'kept_ids':[changed['activities'][0]['id']]})
    assert client.post(route,headers=headers(a),json={'activity_id_to_replace':changed['activities'][0]['id']}).status_code==422


def test_compose_cross_cards_recalculates_and_refuses_overlap_foreign_pool(client):
    _,a,b=ready(client);data=search(client,a).json()
    proposals=data['proposals']
    selection=[proposals[0]['activities'][0]['id'],proposals[1]['activities'][1]['id']]
    response=client.post('/api/dates/compose',headers=headers(a),json={'search_id':data['search_id'],'selected_activity_ids':selection[::-1]})
    assert response.status_code==200,response.text
    plan=response.json();assert [x['id'] for x in plan['activities']]==selection
    assert plan['estimated_total_eur']==sum(a['price_per_person']*2 for a in plan['activities'])
    assert plan['id'] not in {p['id'] for p in proposals}
    assert client.post('/api/dates/compose',headers=headers(b),json={'search_id':data['search_id'],'selected_activity_ids':selection}).status_code==404
    other,foreign,_=ready(client)
    assert client.post('/api/dates/'+proposals[0]['id']+'/replace-activity',headers=headers(foreign),json={'activity_id_to_replace':selection[0]}).status_code==404
    assert client.post('/api/dates/compose',headers=headers(a),json={'selected_activity_ids':[selection[0]]*2}).status_code==422
    assert client.post('/api/dates/compose',headers=headers(a),json={'selected_activity_ids':['unseen']}).status_code==422


def test_new_memory_exclusion_and_catalog_change_block_saved_pool(client):
    _,a,_=ready(client);data=search(client,a).json();plan=data['proposals'][0]
    keep=plan['activities'][1]
    db=client.app.state.v2['db']
    with db.connect() as c:
        row=json.loads(c.execute('SELECT payload FROM v2_activities WHERE id=?',(keep['id'],)).fetchone()[0])
        row['price_per_person']+=1
        c.execute('UPDATE v2_activities SET payload=? WHERE id=?',(json.dumps(row),keep['id']))
    response=client.post('/api/dates/'+plan['id']+'/replace-activity',headers=headers(a),json={'activity_id_to_replace':plan['activities'][0]['id']})
    assert response.status_code==422
    unchanged=client.get('/api/v2/date-plans/'+plan['id'],headers=headers(a)).json()
    assert unchanged['activities']==plan['activities']


def test_explicit_dinner_and_walk_covers_both_categories(client):
    _,a,_=ready(client)
    data=search(client,a,text='Un dîner puis une balade').json()
    assert len(data['proposals'])==3
    assert all({a['type'] for a in p['activities']}=={'food','outdoors'} for p in data['proposals'])
    assert all([a['type'] for a in p['activities']]==['food','outdoors'] for p in data['proposals'])
    japanese=search(client,a,text='Un japonais puis une balade').json()
    assert len(japanese['proposals'])==3
    for p in japanese['proposals']:
        assert [a['type'] for a in p['activities']]==['food','outdoors']
        source=client.app.state.v2['catalog'].get(p['activities'][0]['id'])
        assert 'japanese' in source['tags']


def test_shortage_is_explicit_and_accepted_plan_cannot_change(client):
    _,a,_=ready(client)
    db=client.app.state.v2['db']
    client.app.state.web_provider.override=lambda activities:activities[:1]
    response=search(client,a,activity_count=1).json()
    assert len(response['proposals'])==1 and response['warnings']
    pid=response['proposals'][0]['id']
    assert client.patch('/api/v2/date-plans/'+pid,headers=headers(a),json={'status':'accepted'}).status_code==200
    assert client.post('/api/dates/'+pid+'/replace-activity',headers=headers(a),json={'activity_id_to_replace':response['proposals'][0]['activities'][0]['id']}).status_code==422


def test_new_dislike_and_expired_pool_cannot_be_composed(client):
    _,a,_=ready(client);data=search(client,a).json();plan=data['proposals'][0]
    memory=client.app.state.v2['memory']
    memory.ingest(plan['couple_id'],'PERSON',a['id'],a['id'],'dislikes','new-refusal',{'values':[plan['activities'][0]['type']]},'COUPLE_RECOMMENDATION','conversation')
    body={'search_id':data['search_id'],'selected_activity_ids':[x['id'] for x in plan['activities']]}
    assert client.post('/api/dates/compose',headers=headers(a),json=body).status_code==422
    db=client.app.state.v2['db']
    with db.connect() as c:
        records=c.execute('SELECT id,payload FROM v2_plans').fetchall()
        for record in records:
            value=json.loads(record['payload']);value['_deck']['created_at']='2020-01-01T00:00:00+00:00'
            c.execute('UPDATE v2_plans SET payload=? WHERE id=?',(json.dumps(value),record['id']))
    r=client.post('/api/dates/compose',headers=headers(a),json=body)
    assert r.status_code==422 and '24 h' in r.text


def test_pipelex_adapter_fallback_and_identical_score_validation(monkeypatch):
    from backend.integrations import date_scoring
    monkeypatch.setenv('DATE_SCORING_BACKEND','pipelex')
    def missing(*args):raise ImportError('not installed')
    monkeypatch.setattr(date_scoring,'_pipelex',missing)
    rows,backend,fallback=date_scoring.score([],100,10)
    assert rows==[] and backend=='local_deterministic' and fallback
    monkeypatch.setattr(date_scoring,'_pipelex',lambda *args:[])
    assert date_scoring.score([],100,10)==([], 'pipelex_local', None)
    monkeypatch.setattr(date_scoring,'_pipelex',lambda *args:[{'invented':True}])
    assert date_scoring.score([],100,10)[1]=='local_deterministic'


def test_pipelex_bundle_has_defined_pipes_and_deterministic_entrypoint():
    import tomllib
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'integrations/pipelex_dates/date_scoring.mthds'
    bundle=tomllib.loads(path.read_text())
    assert bundle['main_pipe']=='score_candidates'
    steps=bundle['pipe']['score_candidates']['steps']
    assert all(step['pipe'] in bundle['pipe'] for step in steps)
    assert bundle['pipe']['compute_final_score']['type']=='PipeFunc'
