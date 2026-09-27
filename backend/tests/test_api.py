"""Browserless authenticated V2 lifecycle, privacy and upload regression gates."""
import base64
import json
import socket

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app

PREFIX = '/api/v2'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    monkeypatch.setenv('OPENAI_ENABLED', '0')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('CHANDELLE_DEV', raising=False)
    def denied(*args, **kwargs):
        raise AssertionError('Automated V2 API tests must never open network connections')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)


@pytest.fixture
def client(tmp_path,monkeypatch):
    from backend.tests.web_provider import install
    app=create_app(tmp_path/'v2.sqlite3')
    install(app,monkeypatch)
    with TestClient(app) as client:
        yield client


def headers(member):
    return {'X-Member-Token':member['token']}


def create(client):
    response=client.post(PREFIX+'/onboarding/couples', json={'person_a':'Alex','person_b':'Sam'})
    assert response.status_code == 200, response.text
    return response.json()


def answer(client,couple,member,step,value,privacy='COUPLE_RECOMMENDATION'):
    return client.put(f"{PREFIX}/onboarding/couples/{couple['couple_id']}/members/{member['id']}/answers",
                      headers=headers(member),json={'step':step,'value':value,'privacy_scope':privacy})


def interview(client,couple,member,private):
    values=[{'name':member['name']},{'values':['culture','food','outdoors']},{'values':[]},
            {'min':0,'max':150,'unit':'couple','flexible':False},{'novelty':.7},
            {'days':[],'travel_minutes':60,'dietary':[],'accessibility':[]},{'text':private}]
    for step,value in enumerate(values,1):
        response=answer(client,couple,member,step,value,'PRIVATE' if step==7 else 'COUPLE_RECOMMENDATION')
        assert response.status_code==200,response.text
    return client.post(f"{PREFIX}/onboarding/couples/{couple['couple_id']}/members/{member['id']}/complete",headers=headers(member))


def ready(client):
    couple=create(client)
    a,b=couple['members']
    assert interview(client,couple,a,'A_PRIVATE_ONBOARDING_SENTINEL').status_code==200
    assert interview(client,couple,b,'B_PRIVATE_ONBOARDING_SENTINEL').status_code==200
    return couple,a,b


def query(client,member,**extra):
    response=client.post(PREFIX+'/recommendations/query',headers=headers(member),json={
        'text':'A thoughtful date under 140','activity_count':2,'max_plans':1,
        'time_window':{'start':'2026-09-26T18:00:00','end':'2026-09-26T23:00:00'},**extra})
    assert response.status_code==200,response.text
    return response.json()


def test_real_discovery_requires_explicit_web_search(client):
    _,member,_=ready(client)
    assert client.get(PREFIX+'/activities/real',headers=headers(member)).json()['items']==[]
    result=query(client,member)
    assert result['activities'] and all(not a['demo'] for a in result['activities'])


def test_first_run_resume_idempotency_private_handoff_and_unlock(client):
    couple=create(client);a,b=couple['members'];cid=couple['couple_id']
    assert client.get(PREFIX+'/activities',headers=headers(a)).status_code==409
    first=answer(client,couple,a,1,{'name':'Alex'})
    assert first.status_code==200
    second=answer(client,couple,a,1,{'name':'Alex'})
    assert first.json()==second.json()
    with client.app.state.v2['db'].connect() as con:
        assert con.execute("SELECT COUNT(*) FROM v2_events WHERE entity_id=? AND source='onboarding'",(a['id'],)).fetchone()[0]==1
    resume=client.get(f'{PREFIX}/onboarding/couples/{cid}/members/{a["id"]}',headers=headers(a)).json()
    assert resume['current_step']==2
    assert len(resume['answers'])==1
    assert interview(client,couple,a,'A_PRIVATE_ONBOARDING_SENTINEL').status_code==200
    status=client.get(PREFIX+'/onboarding/status',params={'couple_id':cid}).json()
    assert not status['completed']
    assert 'A_PRIVATE_ONBOARDING_SENTINEL' not in json.dumps(status)
    assert client.get(PREFIX+'/date-plans',headers=headers(b)).status_code==409
    assert client.get(f'{PREFIX}/onboarding/couples/{cid}/members/{a["id"]}',headers=headers(b)).status_code==403
    own=client.get(f'{PREFIX}/onboarding/couples/{cid}/members/{b["id"]}',headers=headers(b)).json()
    assert own['answers']==[]
    assert interview(client,couple,b,'B_PRIVATE_ONBOARDING_SENTINEL').json()['completed']
    completed=client.post(f'{PREFIX}/onboarding/couples/{cid}/members/{b["id"]}/complete',headers=headers(b)).json()
    assert completed['completed']
    assert client.get(PREFIX+'/activities',headers=headers(a)).status_code==200
    for person,other in [(a,b),(b,a)]:
        response=client.get(PREFIX+'/memories',headers=headers(person))
        assert response.status_code==200
        assert ('A_PRIVATE_ONBOARDING_SENTINEL' if person==a else 'B_PRIVATE_ONBOARDING_SENTINEL') in response.text
        assert ('B_PRIVATE_ONBOARDING_SENTINEL' if person==a else 'A_PRIVATE_ONBOARDING_SENTINEL') not in response.text
        assert client.get(PREFIX+'/memories',params={'entity_id':other['id']},headers=headers(person)).status_code==403
        assert client.get(PREFIX+'/memories/search',params={'scope':'PERSON','entity_id':other['id'],'query':'PRIVATE'},headers=headers(person)).status_code==403
    profile=client.get(f'{PREFIX}/couples/{cid}/profile',headers=headers(a))
    assert profile.status_code==200
    assert 'PRIVATE_ONBOARDING_SENTINEL' not in profile.text
    assert 'culture' in profile.json()['interests']


def test_complete_lifecycle_review_photo_memory_suggestion_and_reopen(client,tmp_path):
    couple,a,b=ready(client)
    suggestion=client.post(PREFIX+'/suggestions/check',headers=headers(a)).json()
    assert suggestion['triggered'] is True
    run=query(client,a)
    stages=[stage['stage'] for stage in run['trace']]
    assert stages[:5]==['request','parse','calendar_window','web_search','schema_and_citations']
    assert {'region_idf','budget','availability','time_window','composition'} <= set(stages)
    for stage in run['trace']:
        if 'removed' in stage:
            assert stage['before'] >= stage['after'] >= 0
    assert 'PRIVATE_ONBOARDING_SENTINEL' not in json.dumps(run)
    plan=run['plans'][0];pid=plan['id']
    assert 1<=len(plan['activities'])<=2
    assert plan['total_couple_cost']<=140
    assert client.get(PREFIX+'/runs/'+run['run_id'],headers=headers(a)).status_code==200
    assert client.patch(PREFIX+'/date-plans/'+pid,headers=headers(a),json={'status':'accepted'}).status_code==200
    upload=client.post(PREFIX+'/uploads',params={'plan_id':pid},headers={**headers(a),'Content-Type':'image/png','X-Filename':'../../outside.png'},content=PNG)
    assert upload.status_code==200,upload.text
    photo=upload.json()['id']
    fetched=client.get(PREFIX+'/uploads/'+photo,headers=headers(a))
    assert fetched.content==PNG
    assert fetched.headers['x-content-type-options']=='nosniff'
    assert client.get(PREFIX+'/uploads/'+photo,headers=headers(b)).status_code==404
    review={'rating':5,'activity_ratings':{plan['activities'][0]['id']:5},'text':'A_PRIVATE_REVIEW_SENTINEL',
            'repeat':['culture'],'avoid':[],'privacy_scope':'PRIVATE','idempotency_key':'review-one'}
    response=client.post(f'{PREFIX}/date-plans/{pid}/feedback',headers=headers(a),json=review)
    assert response.status_code==200,response.text
    assert response.json()['status']=='completed'
    assert client.post(f'{PREFIX}/date-plans/{pid}/feedback',headers=headers(a),json=review).status_code==200
    assert client.post(f'{PREFIX}/date-plans/{pid}/feedback',headers=headers(a),json={**review,'rating':1}).status_code==422
    own=client.get(PREFIX+'/history/'+pid,headers=headers(a))
    partner=client.get(PREFIX+'/history/'+pid,headers=headers(b))
    assert 'A_PRIVATE_REVIEW_SENTINEL' in own.text
    assert 'A_PRIVATE_REVIEW_SENTINEL' not in partner.text
    assert partner.json()['photos']==[]
    memories=client.get(PREFIX+'/memories',headers=headers(a)).json()['items']
    assert any(f['source']=='review' for f in memories)
    regenerated=client.post(PREFIX+'/suggestions/'+suggestion['id']+'/action',headers=headers(a),json={'action':'regenerate'})
    assert regenerated.status_code==200,regenerated.text
    changed=regenerated.json()
    assert changed['id']!=suggestion['id']
    assert changed['opportunity_score']<suggestion['opportunity_score']
    assert 'PRIVATE' not in json.dumps(changed)
    with TestClient(create_app(tmp_path/'v2.sqlite3')) as reopened:
        assert reopened.get(PREFIX+'/history/'+pid,headers=headers(a)).json()['status']=='completed'
        assert reopened.get(PREFIX+'/uploads/'+photo,headers=headers(a)).content==PNG
        assert reopened.get(PREFIX+'/onboarding/status',params={'couple_id':couple['couple_id']}).json()['completed']
    assert client.delete(PREFIX+'/uploads/'+photo,headers=headers(a)).json()['deleted']
    assert client.get(PREFIX+'/uploads/'+photo,headers=headers(a)).status_code==404


def test_memory_edit_share_revoke_delete_and_onboarding_correction(client):
    couple,a,b=ready(client);cid=couple['couple_id']
    fact=client.post(PREFIX+'/memories',headers=headers(a),json={'entity_id':a['id'],'category':'interests','key':'manual-cinema','value':{'values':['cinema']}}).json()
    mid=fact['id']
    assert client.patch(PREFIX+'/memories/'+mid,headers=headers(b),json={'value':'intrusion'}).status_code==403
    assert client.post(PREFIX+'/memories/'+mid+'/share',headers=headers(a),json={'privacy_scope':'SHARED'}).status_code==200
    assert 'cinema' in client.get(f'{PREFIX}/couples/{cid}/profile',headers=headers(b)).json()['interests']
    assert client.post(PREFIX+'/memories/'+mid+'/share',headers=headers(a),json={'privacy_scope':'PRIVATE'}).status_code==200
    assert 'cinema' not in client.get(f'{PREFIX}/couples/{cid}/profile',headers=headers(b)).json()['interests']
    assert answer(client,couple,a,2,{'values':['cinema']},'COUPLE_RECOMMENDATION').status_code==200
    profile=client.get(f'{PREFIX}/profiles/PERSON/{a["id"]}',headers=headers(a)).json()
    assert 'cinema' in profile['interests']
    with client.app.state.v2['db'].connect() as con:
        facts=con.execute("SELECT supersedes FROM v2_facts WHERE entity_id=? AND key='onboarding:2'",(a['id'],)).fetchall()
        assert any(row['supersedes'] for row in facts)
    assert client.delete(PREFIX+'/memories/'+mid,headers=headers(a)).json()['deleted']


def test_cross_couple_authorization_and_error_envelopes(client):
    couple,a,b=ready(client);other,x,y=ready(client)
    plan=query(client,a)['plans'][0]
    for path in [f'/date-plans/{plan["id"]}',f'/history/{plan["id"]}',f'/couples/{couple["couple_id"]}/profile']:
        response=client.get(PREFIX+path,headers=headers(x))
        assert response.status_code in (403,404)
        assert set(response.json())=={'error'}
    assert client.get(PREFIX+'/activities').status_code in (401,403)
    for path in ['/activities/missing','/date-plans/missing','/uploads/missing','/runs/missing']:
        response=client.get(PREFIX+path,headers=headers(a))
        assert response.status_code==404
        assert 'error' in response.json()
    assert client.post(PREFIX+'/recommendations/query',headers=headers(a),json={'activity_count':9}).status_code==422
    assert client.get(PREFIX+'/activities',headers=headers(a),params={'limit':0}).status_code==422
    assert client.post(PREFIX+'/dev/seed').status_code==403
    assert client.post(PREFIX+'/dev/reset',json={'confirmation':'RESET LOCAL V2'}).status_code==403


@pytest.mark.parametrize('mime,filename,data,expected',[
    ('text/html','photo.html',b'<script>alert(1)</script>',422),
    ('image/png','photo.jpg',PNG,422),
    ('image/png','photo.png',b'not a png',422),
    ('image/jpeg','photo.jpg',b'not a jpeg',422),
    ('image/png','photo.png',b'',422),
    ('image/png','photo.png',b'x'*(5*1024*1024+1),413),
],ids=['html','extension','invalid-png','invalid-jpeg','empty','oversize'])
def test_upload_rejections(client,mime,filename,data,expected):
    _,a,_=ready(client);pid=query(client,a)['plans'][0]['id']
    response=client.post(PREFIX+'/uploads',params={'plan_id':pid},headers={**headers(a),'Content-Type':mime,'X-Filename':filename},content=data)
    assert response.status_code==expected,response.text
    with client.app.state.v2['db'].connect() as con:
        assert con.execute('SELECT COUNT(*) FROM v2_uploads').fetchone()[0]==0


def test_replacement_keeps_selected_stop_and_suggestion_actions(client):
    _,a,_=ready(client);plan=query(client,a)['plans'][0];pid=plan['id']
    assert len(plan['activities'])==2
    keep,replace=plan['activities']
    assert client.patch(PREFIX+'/date-plans/'+pid,headers=headers(a),json={'kept_ids':[keep['id']]}).status_code==200
    response=client.post(f'{PREFIX}/date-plans/{pid}/replace',headers=headers(a),json={'activity_id':keep['id']})
    assert response.status_code==422
    response=client.post(f'{PREFIX}/date-plans/{pid}/replace',headers=headers(a),json={'activity_id':replace['id']})
    assert response.status_code==200,response.text
    assert keep['id'] in [x['id'] for x in response.json()['activities']]
    assert replace['id'] not in [x['id'] for x in response.json()['activities']]
    suggestion=client.post(PREFIX+'/suggestions/check',headers=headers(a)).json();sid=suggestion['id']
    assert client.post(PREFIX+'/suggestions/check',headers=headers(a)).json()['id']==sid
    for action in ['viewed','snoozed','dismissed']:
        result=client.post(f'{PREFIX}/suggestions/{sid}/action',headers=headers(a),json={'action':action})
        assert result.status_code==200,result.text
        assert result.json()['state']==action
    assert client.post(PREFIX+'/suggestions/check',headers=headers(a)).json()['triggered'] is False


def test_interrupted_onboarding_reopens_without_private_handoff_leak(client,tmp_path):
    couple=create(client);a,b=couple['members'];cid=couple['couple_id']
    assert answer(client,couple,a,1,{'name':'PRIVATE_IDENTITY_SENTINEL'},'PRIVATE').status_code==200
    assert answer(client,couple,a,2,{'values':['culture']},'COUPLE_RECOMMENDATION').status_code==200
    with TestClient(create_app(tmp_path/'v2.sqlite3')) as resumed:
        status=resumed.get(PREFIX+'/onboarding/status',params={'couple_id':cid})
        assert 'PRIVATE_IDENTITY_SENTINEL' not in status.text
        own=resumed.get(f'{PREFIX}/onboarding/couples/{cid}/members/{a["id"]}',headers=headers(a)).json()
        assert own['current_step']==3
        assert own['answers'][0]['value']['name']=='PRIVATE_IDENTITY_SENTINEL'
        assert resumed.get(PREFIX+'/activities',headers=headers(b)).status_code==409
        complete=resumed.post(f'{PREFIX}/onboarding/couples/{cid}/members/{a["id"]}/complete',headers=headers(a))
        assert complete.status_code==422
        assert 'PRIVATE_IDENTITY_SENTINEL' not in complete.text


@pytest.mark.parametrize('step,value',[(1,{'name':42}),(1,{'name':None}),(6,{'travel_minutes':'bad'}),(6,{'travel_minutes':None}),(6,{'dietary':[{}]}),(5,{'energy':2}),(4,{'min':50,'max':10})])
def test_invalid_interview_answers_return_validation_error(client,step,value):
    couple=create(client);a=couple['members'][0]
    response=answer(client,couple,a,step,value)
    assert response.status_code==422,response.text
    assert set(response.json())=={'error'}


def test_private_conversation_and_date_memory_are_owner_scoped(client):
    _,a,b=ready(client)
    response=client.post(PREFIX+'/conversations',headers=headers(a),json={'text':'I love PRIVATE_CONVERSATION_SENTINEL','privacy_scope':'PRIVATE'})
    assert response.status_code==200,response.text
    assert response.json()['facts']
    partner=client.get(PREFIX+'/memories',headers=headers(b))
    assert 'PRIVATE_CONVERSATION_SENTINEL' not in partner.text
    session=response.json()['conversation_id']
    assert client.get(PREFIX+'/memories',headers=headers(b),params={'scope':'SESSION','entity_id':session}).status_code==403
    plan=query(client,a)['plans'][0];pid=plan['id']
    assert client.patch(PREFIX+'/date-plans/'+pid,headers=headers(a),json={'status':'accepted'}).status_code==200
    assert client.post(f'{PREFIX}/date-plans/{pid}/feedback',headers=headers(a),json={'rating':4,'text':'PRIVATE_DATE_MEMORY_SENTINEL','privacy_scope':'PRIVATE','idempotency_key':'scope-review'}).status_code==200
    owner=client.get(PREFIX+'/memories',headers=headers(a),params={'scope':'DATE','entity_id':pid})
    partner=client.get(PREFIX+'/memories',headers=headers(b),params={'scope':'DATE','entity_id':pid})
    assert owner.status_code==partner.status_code==200
    assert 'PRIVATE_DATE_MEMORY_SENTINEL' in owner.text
    assert 'PRIVATE_DATE_MEMORY_SENTINEL' not in partner.text


def test_activity_feedback_neutral_clears_previous_rejection(client):
    _,a,_=ready(client)
    result=query(client,a,categories=['culture'],activity_count=1)
    aid=result['activities'][0]['id']
    path=PREFIX+'/activities/'+aid+'/state'
    assert client.post(path,headers=headers(a),json={'state':'disliked'}).status_code==200
    assert client.post(path,headers=headers(a),json={'state':'liked'}).status_code==200
    liked=client.get(f'{PREFIX}/profiles/PERSON/{a["id"]}',headers=headers(a)).json()
    assert 'culture' not in liked['dislikes']
    assert 'culture' in liked['interests']
    assert client.post(path,headers=headers(a),json={'state':'neutral'}).status_code==200
    profile=client.get(f'{PREFIX}/profiles/PERSON/{a["id"]}',headers=headers(a)).json()
    assert 'culture' not in profile['dislikes']
    response=client.post(PREFIX+'/recommendations/query',headers=headers(a),json={'text':'culture','categories':['culture'],'activity_count':1,'max_plans':1})
    assert response.status_code==200,response.text


def test_suggestion_acceptance_is_repeatable_and_persists_plan(client):
    _,a,b=ready(client)
    suggestion=client.post(PREFIX+'/suggestions/check',headers=headers(a)).json()
    path=f'{PREFIX}/suggestions/{suggestion["id"]}/action'
    for _ in range(2):
        response=client.post(path,headers=headers(a),json={'action':'accepted'})
        assert response.status_code==200,response.text
        assert response.json()['state']=='accepted'
    plan=client.get(PREFIX+'/date-plans/'+suggestion['plan']['id'],headers=headers(b)).json()
    assert plan['status']=='accepted'
    assert client.get(PREFIX+'/history',headers=headers(b)).json()['total']>=1


def test_private_memory_does_not_change_partner_suggestion_signal(client):
    _,a,b=ready(client)
    # Remove the saturation caused by recent onboarding so this assertion detects
    # even one unauthorized private fact in the proactive change count.
    with client.app.state.v2['db'].connect() as con:
        con.execute("UPDATE v2_facts SET updated_at='2020-01-01T00:00:00+00:00'")
    first=client.post(PREFIX+'/suggestions/check',headers=headers(b)).json()
    private=client.post(PREFIX+'/memories',headers=headers(a),json={
        'entity_id':a['id'],'category':'experience','key':'private-new-change',
        'value':'PRIVATE_PROACTIVE_SIGNAL_SENTINEL','privacy_scope':'PRIVATE'})
    assert private.status_code==200
    changed=client.post(f'{PREFIX}/suggestions/{first["id"]}/action',headers=headers(b),json={'action':'regenerate'}).json()
    assert changed['opportunity_score']==first['opportunity_score']
    assert changed['trigger_reasons']==first['trigger_reasons']
    assert 'PRIVATE_PROACTIVE_SIGNAL_SENTINEL' not in json.dumps(changed)


"""Final V2 migration, selected activity and validation checks."""
import json
import subprocess
import sys
from fastapi.testclient import TestClient
from backend.api.app import create_app
from backend.db import Database


def seeded(tmp_path,monkeypatch):
    monkeypatch.setenv('CHANDELLE_DEV','1')
    client=TestClient(create_app(tmp_path/'system.sqlite3'))
    couple=client.post('/api/v2/dev/seed').json()
    return client,{'X-Member-Token':couple['members'][0]['token']},couple


def test_required_web_activity_and_activity_cap(client):
    _,a,_=ready(client)
    initial=query(client,a,activity_count=1)
    aid=initial['activities'][0]['id']
    result=query(client,a,activity_count=1,required_activity_id=aid)
    assert result['plans'] and all(p['activities'][0]['id']==aid for p in result['plans'])
    result=query(client,a,required_activity_id='invented-unknown-id')
    assert result['plans']==[] and result['warnings']


def test_schema_reopen_in_independent_process_preserves_legacy(tmp_path):
    path=tmp_path/'migration.sqlite'
    db=Database(path)
    with db.connect() as c:
        c.execute('CREATE TABLE couple_profiles(couple_id TEXT PRIMARY KEY,payload TEXT)')
        c.execute('INSERT INTO couple_profiles VALUES(?,?)',('legacy','{"preserved":true}'))
        c.execute('INSERT INTO v2_couples(id,created_at) VALUES(?,?)',('durable','2026-09-26'))
    source="""
import json,sys
from backend.db import Database
with Database(sys.argv[1]).connect() as c:
 print(json.dumps([c.execute('SELECT COUNT(*) FROM v2_schema').fetchone()[0],c.execute('SELECT id FROM v2_couples').fetchone()[0],c.execute('SELECT payload FROM couple_profiles').fetchone()[0]]))
"""
    process=subprocess.run([sys.executable,'-c',source,str(path)],check=True,capture_output=True,text=True)
    assert json.loads(process.stdout)==[1,'durable','{"preserved":true}']


def test_memory_patch_rejects_null_wrong_types_and_provenance_is_private(tmp_path,monkeypatch):
    client,headers,couple=seeded(tmp_path,monkeypatch)
    person=couple['members'][0]
    fact=client.post('/api/v2/memories',headers=headers,json={'entity_id':person['id'],'category':'interests','key':'private','value':'private sentinel'}).json()
    for body in ({'salience':'bad'},{'confidence':None},{'privacy_scope':None},{'unknown':'field'}):
        assert client.patch('/api/v2/memories/'+fact['id'],headers=headers,json=body).status_code==422
    assert client.get('/api/v2/memories/'+fact['id']+'/provenance',headers=headers).status_code==200
    other={'X-Member-Token':couple['members'][1]['token']}
    result=client.get('/api/v2/memories/'+fact['id']+'/provenance',headers=other)
    assert result.status_code==403 and 'private sentinel' not in result.text


def test_v2_default_page_legacy_and_dev_reset(tmp_path,monkeypatch):
    client,headers,couple=seeded(tmp_path,monkeypatch)
    assert '/v2-static/app.mjs' in client.get('/').text
    assert '/static/app.js' in client.get('/v1/demo').text
    assert client.post('/api/v2/dev/reset',json={'confirmation':'wrong'}).status_code==422
    response=client.post('/api/v2/dev/reset',json={'confirmation':'RESET LOCAL V2'})
    assert response.status_code==200,response.text
    assert client.get('/api/v2/onboarding/status',params={'couple_id':couple['couple_id']}).status_code==404
    assert client.get('/health').status_code==200


def test_personal_erasure_removes_raw_answers_and_private_events(tmp_path,monkeypatch):
    client,headers,couple=seeded(tmp_path,monkeypatch)
    uid=couple['members'][0]['id'];other=couple['members'][1]['id']
    assert client.request('DELETE','/api/v2/users/me/data',headers=headers,json={'confirmation':'DELETE MY DATA'}).status_code==200
    db=client.app.state.v2['db']
    with db.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM v2_answers WHERE user_id=?',(uid,)).fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM v2_facts WHERE owner_id=?',(uid,)).fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM v2_events WHERE entity_id=?',(uid,)).fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM v2_answers WHERE user_id=?',(other,)).fetchone()[0]==7
    assert client.get('/api/v2/date-plans',headers=headers).status_code==409
