"""Provider simulations, real authenticated API/SQLite. Never makes a network call."""
import json
from types import SimpleNamespace
from datetime import datetime,timedelta,timezone
import pytest
from backend.tests.test_api import client,offline_only,ready,headers
from backend.integrations.openai import OpenAIAdapter,ParsedRequest
from backend.streams.C_discovery.web import WebDiscovery

START=(datetime.now(timezone.utc)+timedelta(days=3)).replace(hour=18,minute=0,second=0,microsecond=0)

def fact(index=0,**changes):
    # Test response only, built on demand; never a deployable catalogue.
    start=START+timedelta(minutes=90*index)
    return dict(name=f'Lieu de test {index}',category='food' if index%2==0 else 'outdoors',kind='place',
        source_url=f'https://www.paris.fr/pages/test-{index}',description='Réponse fournisseur simulée.',
        address='Paris',department='75',location={'lat':48.86,'lng':2.35},tags=['japanese'] if index%2==0 else ['walking'],
        price=10 if index%2==0 else 0,price_unit='person' if index%2==0 else 'free',
        start=start.isoformat(),end=(start+timedelta(minutes=60)).isoformat(),schedule_status='proposed',
        availability='unknown',evidence='Valeurs simulées dans un test.',**{}) | changes

class Provider:
    def __init__(self,rows):self.rows=rows;self.responses=self;self.calls=[]
    def create(self,**kw):
        self.calls.append(kw)
        data={'status':'completed','output':[{'type':'web_search_call','status':'completed',
              'action':{'sources':[{'url':r['source_url']} for r in self.rows if not r.get('uncited')]}},
              {'type':'message','content':[{'type':'output_text','text':json.dumps({'activities':[{k:v for k,v in r.items() if k!='uncited'} for r in self.rows],'note':''}),'annotations':[]}]}]}
        return SimpleNamespace(model_dump=lambda:data,usage=SimpleNamespace(model_dump=lambda:{}))

def configure(client,monkeypatch,rows):
    monkeypatch.setenv('OPENAI_ENABLED','1');monkeypatch.setenv('OPENAI_WEB_ENABLED','1')
    monkeypatch.setenv('OPENAI_DAILY_RESERVE_USD','10')
    def parse(self,text):
        self.last_mode='openai';self.last_fallback=None
        return ParsedRequest(categories=['restaurant','balade'],budget=100)
    monkeypatch.setattr(OpenAIAdapter,'parse',parse)
    state=client.app.state.v2;provider=Provider(rows)
    state['planning'].web=WebDiscovery(state['db'],state['memory'],provider)
    return provider

def search(client,a,**values):
    constraints={'text':'Un japonais puis une balade','mode':'auto','activity_count':2,
         'time_window':{'start':START.isoformat(),'end':(START+timedelta(hours=6)).isoformat()},**values}
    return client.post('/api/v2/dates/search',headers=headers(a),json={'constraints':constraints})

def test_single_web_pipeline_persists_deduplicates_and_composes(client,monkeypatch):
    _,a,b=ready(client);provider=configure(client,monkeypatch,[fact(i) for i in range(4)])
    response=search(client,a);assert response.status_code==200,response.text
    data=response.json();assert len(data['activities'])==4 and data['proposals']
    assert all(not x['demo'] and x['source_url'] for x in data['activities'])
    assert any(t['stage']=='category' and t['after']==4 for t in data['trace'])
    first=data['proposals'][0];ids=[v['id'] for v in first['activities']]
    r=client.post('/api/dates/compose',headers=headers(a),json={'search_id':data['search_id'],'selected_activity_ids':ids})
    assert r.status_code==200,r.text
    assert client.get('/api/v2/runs/'+data['search_id'],headers=headers(b)).status_code==403
    again=search(client,a).json();assert again['cached'] and len(provider.calls)==1
    with client.app.state.v2['db'].connect() as c:assert c.execute('SELECT COUNT(*) FROM v2_activities').fetchone()[0]==4
    assert client.get('/api/v2/activities',headers=headers(a)).json()['items']==[]

def test_unknown_values_are_cards_not_invented_plans(client,monkeypatch):
    _,a,_=ready(client);configure(client,monkeypatch,[fact(price=None,price_unit='unknown',start=None,end=None,location=None,schedule_status='unknown')])
    r=search(client,a).json();assert len(r['activities'])==1 and r['proposals']==[]
    card=r['activities'][0];assert card['price_per_person'] is None and card['start'] is None and not card['composable']
    bad=client.post('/api/dates/compose',headers=headers(a),json={'search_id':r['search_id'],'selected_activity_ids':[card['id']]})
    assert bad.status_code==422

@pytest.mark.parametrize('changes,stage',[
    ({'department':'69'},'region_idf'),({'price':200},'budget'),({'category':'cinema'},'category'),
    ({'availability':'unavailable'},'availability'),({'start':(START-timedelta(hours=6)).isoformat(),'end':(START-timedelta(hours=5)).isoformat()},'time_window'),
    ({'tags':['italian']},'requested_tags'),
    ({'kind':'event','schedule_status':'published','start':'2020-01-01T18:00:00+01:00','end':'2020-01-01T19:00:00+01:00'},'expiration'),
])
def test_each_filter_reports_exact_loss(client,monkeypatch,changes,stage):
    _,a,_=ready(client);configure(client,monkeypatch,[fact(**changes)])
    data=search(client,a).json();assert not data['activities'] and data['empty_reason']=='all_filtered',data
    step=next(t for t in data['trace'] if t['stage']==stage)
    assert step['before']==1 and step['after']==0 and step['removed']==1
    assert data['message']

def test_no_web_results_and_unavailable_are_distinct(client,monkeypatch):
    _,a,_=ready(client);configure(client,monkeypatch,[])
    data=search(client,a).json();assert data['empty_reason']=='no_web_results'
    disabled=search(client,a,mode='offline').json();assert disabled['status']=='unavailable' and disabled['empty_reason']=='web_disabled'

def test_citations_required_and_malformed_partial_result(client,monkeypatch):
    _,a,_=ready(client);configure(client,monkeypatch,[fact(0,uncited=True),fact(1),fact(2,price=-1)])
    data=search(client,a).json();assert len(data['activities'])==1
    stage=next(t for t in data['trace'] if t['stage']=='schema_and_citations')
    assert stage['before']==3 and stage['after']==1 and stage['invalid']==1 and stage['uncited']==1

def test_refresh_updates_same_source_and_failed_provider_does_not_clear_cache(client,monkeypatch):
    _,a,_=ready(client);provider=configure(client,monkeypatch,[fact()])
    data=search(client,a).json();aid=data['activities'][0]['id']
    with client.app.state.v2['db'].connect() as c:c.execute('DELETE FROM v2_web_cache')
    provider.rows=[fact(price=15)]
    assert search(client,a).json()['activities'][0]['price_per_person']==15
    with client.app.state.v2['db'].connect() as c:
        assert c.execute('SELECT COUNT(*) FROM v2_activities').fetchone()[0]==1
        c.execute('DELETE FROM v2_web_cache')
    def fail(**kw):raise TimeoutError()
    provider.create=fail
    data=search(client,a).json();assert data['empty_reason']=='provider_timeout' and not data['activities']
    with client.app.state.v2['db'].connect() as c:assert c.execute('SELECT id FROM v2_activities').fetchone()[0]==aid


def test_live_shape_named_department_and_duplicate_are_normalized(client,monkeypatch):
    _,a,_=ready(client)
    configure(client,monkeypatch,[fact(department='Paris')]*4)
    data=search(client,a).json()
    assert len(data['activities'])==1
    trace={s['stage']:s for s in data['trace']}
    assert trace['region_idf']['after']==4
    assert trace['deduplication']['removed']==3
    assert any('balade' in w for w in data['warnings'])


def test_parsed_invalid_calendar_date_is_not_accepted():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):ParsedRequest(date='2026-02-31')
