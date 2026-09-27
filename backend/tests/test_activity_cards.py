"""Actual local persistence/composition; only provider responses and activity data are synthetic."""
import json
from backend.tests.test_api import client,offline_only,ready,headers
from backend.tests.test_date_deck import search
from backend.tests.test_ai_discovery import Client,enable
from backend.streams.C_discovery.web import WebDiscovery,WebQuery


def test_auto_processing_uses_server_policy_and_keeps_scopes(client,monkeypatch):
    _,a,b=ready(client)
    assert search(client,a,mode='auto').status_code==200
    assert search(client,a,mode='openai').status_code==200  # legacy contract unchanged
    r=client.post('/api/v2/conversations',headers=headers(a),json={'text':"J'aime le jazz",'privacy_scope':'PRIVATE','mode':'auto'})
    assert r.status_code==200 and r.json()['facts']
    assert all(f['privacy_scope']=='PRIVATE' for f in r.json()['facts'])
    assert 'discussion:' not in client.get('/api/v2/memories',headers=headers(b)).text
    state=client.app.state.v2;fake=Client();web=WebDiscovery(state['db'],state['memory'],fake)
    body=WebQuery(text='Une exposition à Paris',processing='standard')
    assert body.cloud_consent is False
    monkeypatch.setenv('OPENAI_WEB_ENABLED','0')
    assert web.search(a,body)['status']=='unavailable' and not fake.calls
    enable(monkeypatch)
    assert web.search(a,body)['status']=='completed'
    assert web.search(a,body)['cached'] is True and len(fake.calls)==1


def test_activity_projection_and_saved_search_are_private(client):
    _,a,b=ready(client);r=search(client,a);assert r.status_code==200
    data=r.json();assert len(data['activities'])>3
    allowed={'id','name','category','start','end','price_per_person','location','address','tags','why','demo','image_url','rating','source'}
    for row in data['activities']:
        assert allowed<=set(row) and not row['demo'] and row['source_url'] and row['image_url'] is None
        assert 'T' in row['start'] and row['why']
    run=client.get('/api/v2/runs/'+data['search_id'],headers=headers(a))
    assert run.status_code==200 and '_activity_search' not in run.text
    assert client.get('/api/v2/runs/'+data['search_id'],headers=headers(b)).status_code==403
    selected=[data['activities'][0]['id']]
    response=client.post('/api/dates/compose',headers=headers(a),json={'search_id':data['search_id'],'selected_activity_ids':selected})
    assert response.status_code==200 and response.json()['status']=='draft'


def set_activities(client,count,overlap=False):
    def change(activities):
        rows=[]
        for i in range(count):
            row=dict(activities[0]);day=row['start'][:10];offset=row['start'][19:]
            hour=19 if overlap else 18+i
            row.update(name=f'Fixed {i}',source_url=f'https://www.paris.fr/pages/fixed-{i}',start=f'{day}T{hour:02}:00:00{offset}',end=f'{day}T{hour:02}:45:00{offset}',price=5,category='culture')
            rows.append(row)
        return rows
    client.app.state.web_provider.override=change


def test_individual_selection_works_even_without_complete_programme(client):
    _,a,_=ready(client);set_activities(client,2,overlap=True)
    data=search(client,a,activity_count=2).json()
    assert data['proposals']==[] and len(data['activities'])==2
    def compose(ids):return client.post('/api/dates/compose',headers=headers(a),json={'search_id':data['search_id'],'selected_activity_ids':ids})
    ids=[v['id'] for v in data['activities']]
    assert compose(ids).status_code==422
    assert compose(ids[:1]).status_code==200
    # Failure never discards the saved search.
    assert len(client.get('/api/v2/runs/'+data['search_id'],headers=headers(a)).json()['activities'])==2


def test_four_step_hand_composition_and_replace_preserve_other_steps(client):
    _,a,_=ready(client);set_activities(client,4)
    data=search(client,a).json()
    ids=[r['id'] for r in data['activities']]
    assert len(ids)==4
    composed=client.post('/api/dates/compose',headers=headers(a),json={'search_id':data['search_id'],'selected_activity_ids':ids[::-1]})
    assert composed.status_code==200,composed.text
    plan=composed.json();assert len(plan['activities'])==4 and plan['estimated_total_eur']==40
    assert [x['name'] for x in plan['activities']]==['Fixed 0','Fixed 1','Fixed 2','Fixed 3']
    fail=client.post('/api/dates/'+plan['id']+'/replace-activity',headers=headers(a),json={'activity_id_to_replace':plan['activities'][1]['id']})
    assert fail.status_code==422
    assert client.get('/api/v2/date-plans/'+plan['id'],headers=headers(a)).json()['activities']==plan['activities']


def test_only_documented_public_catalogue_images():
    from backend.streams.E_orchestrator.activity_choices import catalogue_image
    assert catalogue_image({'image_url':'https://localhost/private'}) is None
    assert catalogue_image({'image_url':'javascript:bad()'}) is None
    assert catalogue_image({'media':[{'url':'https://www.paris.fr/photo.jpg'}]})=='https://paris.fr/photo.jpg'
    assert catalogue_image({}) is None


def test_synthetic_records_are_removed_on_upgrade(client):
    db=client.app.state.v2['db']
    with db.connect() as c:c.execute('INSERT INTO v2_activities VALUES(?,?)',('retired',json.dumps({'demo':True})))
    assert client.app.state.v2['catalog'].remove_synthetic()==1
    assert client.app.state.v2['catalog'].remove_synthetic()==0
