"""Specific neighbourhood queries must reach actual web cards, with the same filters."""
import json
from types import SimpleNamespace
import pytest
from backend.tests.test_api import client, ready, headers, offline_only
from backend.tests.test_dialogue import model, source, turn
from backend.tests.test_imported_catalog import bundle, venue
from backend.integrations.dialogue import DialogueDecision, SearchIntent
from backend.streams.C_discovery.local_catalog import ImportedCatalog
from backend.streams.C_discovery.locations import matches_location


@pytest.mark.parametrize('query',['Paris 14','Paris 14e','Paris 14ème arrondissement','75014','Paris XIV'])
def test_paris_district_uses_postcode_without_confusing_street_numbers(query):
    assert matches_location(query,'3 rue du Test, 75014 Paris')
    assert not matches_location(query,'14 rue du Test, 75015 Paris')
    assert not matches_location(query,'Paris')  # Missing address must trigger research.


def test_generic_words_do_not_empty_catalog_and_location_precedes_limit(client,tmp_path):
    pair,_,_=ready(client)
    rows=[{**venue(i),'title':f'Restaurant test {i}','address':'2 rue Test, 75015 Paris'} for i in range(1,206)]
    rows += [{**venue(i),'title':f'Adresse du 14e {i}','address':'3 rue Test, 75014 Paris'} for i in range(900,904)]
    ImportedCatalog(client.app.state.v2['db']).import_bundle(bundle(tmp_path,rows))
    real=client.app.state.v2['real_recommendations']
    intent=SearchIntent(summary='resto paris 14 budget 40€ max',location='Paris 14e',budget=40,categories=['food'])
    result=real.search(pair['couple_id'],intent)
    assert len(result['items'])==4
    assert all(x['location']['arrondissement']==14 for x in result['items'])
    assert all(x['total_couple_cost'] is None for x in result['items'])


def web_venue(name,price=18,address='3 rue Test, 75014 Paris'):
    return {'name':name,'category':'food','kind':'place','source_url':'https://example.org/'+name,
        'description':'Menu documenté par le fournisseur simulé.','address':address,
        'price':price,'price_unit':'person' if price is not None else 'unknown',
        'tags':['restaurant'],'schedule_status':'unknown','availability':'unknown'}


def test_paris14_web_results_become_four_grounded_cards_and_keep_budget(client,monkeypatch):
    _,a,_=ready(client);source(client,[])
    intent=SearchIntent(summary='resto paris 14 budget 40€ max',location='Paris 14e',budget=40,categories=['food'])
    fake=model(client,monkeypatch,[DialogueDecision(action='discover',reply='Je cherche.',intent=intent)])
    rows=[web_venue('A',20),web_venue('B',18),web_venue('C',15),web_venue('D',None),
          web_venue('Too-expensive',40),web_venue('Wrong-district',18,'14 rue Test, 75015 Paris'),web_venue('Unknown-district',18,'Paris')]
    calls=[]
    def search(member,body):
        calls.append(body)
        return {'status':'completed','activities':rows,'answer':'Unfiltered provider note',
            'sources':[{'url':r['source_url'],'title':r['name']} for r in rows]}
    client.app.state.v2['dialogue'].web=SimpleNamespace(search=search)
    result=turn(client,a,intent.summary,cloud_consent=True,web_consent=True)
    assert len(calls)==2 and calls[0].area=='Paris 14e' and calls[0].result_limit==8
    assert calls[1].refinement  # Fourth card has an unknown price; try to document it.
    assert '40 EUR pour deux' in calls[0].text
    assert '20 EUR PAR PERSONNE' in calls[0].text
    assert {x['name'] for x in result['suggestions']}=={'A','B','C','D'}
    assert all(x['total_couple_cost'] is None or x['total_couple_cost']<=40 for x in result['suggestions'])
    assert result['suggestions'][-1]['total_couple_cost'] is None
    assert result['mode']=='openai' and result['diagnostic'] is None
    payload=json.loads(fake.calls[1]['input'])
    assert len(payload['result']['activities'])==4
    assert payload['result']['budget_check']=={'total_budget_for_two':40,'known_price_count':3,'unknown_price_names':['D']}
    assert 'Unfiltered provider note' not in fake.calls[1]['input']
    with client.app.state.v2['db'].connect() as c:
        assert c.execute("SELECT count(*) FROM v2_activities WHERE json_extract(payload,'$.provider')='openai_web'").fetchone()[0]==7


def test_missing_prices_trigger_web_even_with_four_local_cards(client,monkeypatch):
    from backend.tests.test_dialogue import activity, decision
    _,a,_=ready(client)
    source(client,[activity(str(i),name=f'Lieu {i}',price_per_person=None) for i in range(4)])
    model(client,monkeypatch,[decision(budget=40)])
    calls=[]
    def unavailable(member,body):
        calls.append(body)
        return {'status':'unavailable','reason':'provider_timeout'}
    client.app.state.v2['dialogue'].web=SimpleNamespace(search=unavailable)
    result=turn(client,a,'Paris, 40 euros pour deux',cloud_consent=True,web_consent=True)
    assert len(calls)==1 and len(result['suggestions'])==4
    assert result['diagnostic']['code']=='provider_timeout'
    assert 'disponibilité commune' not in result['reply']


@pytest.mark.parametrize('complement_fails',[False,True])
def test_web_complements_after_filtering_and_preserves_first_results_on_failure(client,monkeypatch,complement_fails):
    _,a,_=ready(client);source(client,[])
    intent=SearchIntent(summary='resto paris 14 budget 40€ max',location='Paris 14e',budget=40,categories=['food'])
    model(client,monkeypatch,[DialogueDecision(action='discover',reply='Je cherche.',intent=intent)])
    calls=[]
    def search(member,body):
        calls.append(body)
        if len(calls)==2 and complement_fails:
            return {'status':'unavailable','reason':'budget_limit_reached'}
        rows=([web_venue('A',17),web_venue('Too-expensive',31)] if len(calls)==1
              else [web_venue('A',17),web_venue('B',18),web_venue('C',15),web_venue('D',20)])
        return {'status':'completed','activities':rows,'answer':'Note brute',
                'sources':[{'url':r['source_url'],'title':r['name']} for r in rows]}
    client.app.state.v2['dialogue'].web=SimpleNamespace(search=search)
    result=turn(client,a,intent.summary,cloud_consent=True,web_consent=True)
    assert len(calls)==2 and not calls[0].refinement and calls[1].refinement
    assert calls[1].already_seen==['A','Too-expensive']
    assert calls[0].text==calls[1].text and calls[1].area=='Paris 14e'
    assert result['web']['requests']==2
    assert {r['name'] for r in result['suggestions']}==({'A'} if complement_fails else {'A','B','C','D'})
    assert all(r['total_couple_cost']<=40 for r in result['suggestions'])
    if complement_fails:
        assert 'premières pistes sont conservées' in result['warning']
        assert result['web']['refinement_reason']=='budget_limit_reached'


def test_restaurant_price_units_and_complement_cache_are_safe(client,monkeypatch):
    from backend.tests.test_ai_discovery import Client, enable
    from backend.streams.C_discovery.web import WebDiscovery, WebQuery
    from backend.streams.C_discovery.recommendations import DatabaseActivities
    from backend.streams.C_discovery.service import record_web
    pair,a,_=ready(client);source(client,[]);enable(monkeypatch)
    rows=[{**web_venue('Lunch',17),'evidence':'Menu individuel midi'},
          {**web_venue('Dinner',31),'evidence':'Menu individuel'},
          {**web_venue('Ambiguous',17),'price_unit':'couple','evidence':'Prix sans unité fiable'}]
    response=SimpleNamespace(model_dump=lambda:{'status':'completed','output':[
        {'type':'web_search_call','status':'completed','action':{'type':'search','sources':[{'url':r['source_url']} for r in rows]}},
        {'type':'message','content':[{'type':'output_text','text':json.dumps({'activities':rows,'note':''})}]}]})
    fake=Client(response);state=client.app.state.v2
    web=WebDiscovery(state['db'],state['memory'],fake)
    body=WebQuery(text='resto Paris 14, 40 euros pour deux',cloud_consent=True,processing='ask',result_limit=8)
    result=web.search(a,body)
    assert result['status']=='completed'
    assert result['activities'][2]['price'] is None
    assert result['activities'][2]['price_unit']=='unknown'
    records=[DatabaseActivities.adapt(record_web(row,result['searched_at'])) for row in result['activities']]
    found=state['real_recommendations'].search(pair['couple_id'],SearchIntent(location='Paris 14e',budget=40,categories=['food']),extra_records=records)
    assert {r['name']:r['total_couple_cost'] for r in found['items']}=={'Lunch':34,'Ambiguous':None}
    assert web.search(a,body)['cached'] and len(fake.calls)==1
    assert not web.search(a,body.model_copy(update={'refinement':True}))['cached']
    assert 'search_goal' in json.loads(fake.calls[1]['input'])
    legacy=web.search(a,body.model_copy(update={'processing':'legacy'}))
    assert not legacy['cached'] and legacy['activities'][2]['price']==17
