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


def test_required_catalog_activity_and_activity_cap(tmp_path,monkeypatch):
    client,headers,_=seeded(tmp_path,monkeypatch)
    body={'text':'A date','activity_count':1,'required_activity_id':'demo_culture_3'}
    response=client.post('/api/v2/recommendations/query',headers=headers,json=body)
    assert response.status_code==200,response.text
    assert all([a['id'] for a in p['activities']]==['demo_culture_3'] for p in response.json()['plans'])
    body['required_activity_id']='invented-unknown-id'
    assert client.post('/api/v2/recommendations/query',headers=headers,json=body).status_code==422


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
