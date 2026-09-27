"""Conversation → sources → actual planner; all providers are fake and network denied."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
import json
import pytest
from backend.tests.test_api import client, ready, headers, offline_only
from backend.integrations.dialogue import DialogueAdapter, DialogueDecision, SearchIntent, GroundedReply
from backend.streams.H_conversation.dialogue import spoken_budget
from backend.streams.C_discovery.recommendations import RealRecommendations


def turn(client, member, message='', previous=None, **options):
    body={'message':message,'request_id':uuid4().hex,**options}
    if previous: body.update(session_id=previous['session_id'],revision=previous['revision'])
    response=client.post('/api/v2/ask/chat',headers=headers(member),json=body)
    assert response.status_code==200,response.text
    return response.json()


def activity(ident='real_1', **extra):
    start=(datetime.now(timezone.utc)+timedelta(days=7)).replace(hour=17,minute=0,second=0,microsecond=0)
    return {'id':ident,'kind':'event','type':'culture','name':'Atelier de céramique test',
        'description':'Atelier calme et créatif','tags':['creative','quiet'],
        'start':start.isoformat(),'end':(start+timedelta(hours=1)).isoformat(),'opening_hours':None,
        'price_per_person':20,'price_level':None,'location':{'lat':48.8566,'lng':2.3522,'address':'Paris','arrondissement':4},
        'booking_url':None,'website':'https://example.org/atelier','image_url':None,'rating':None,
        'source':'openai_web','match_score':None,'why':None,'attribution':'OpenAI web search',
        'fetched_at':datetime.now(timezone.utc).isoformat(),**extra}


def source(client, rows):
    client.app.state.v2['real_recommendations'].source=SimpleNamespace(activities=lambda:rows)


class FakeSDK:
    def __init__(self, decisions):
        self.decisions=iter(decisions);self.responses=self;self.calls=[]
    def parse(self, **kw):
        self.calls.append(kw)
        if kw['text_format'] is GroundedReply:
            return SimpleNamespace(output_parsed=GroundedReply(candidate_ids=[],
                reply=json.loads(kw['input'])['result']['fallback_reply']),usage=None)
        value=next(self.decisions)
        if isinstance(value,Exception): raise value
        return SimpleNamespace(output_parsed=value,usage=None)


def model(client, monkeypatch, decisions):
    monkeypatch.setenv('OPENAI_ENABLED','1')
    fake=FakeSDK(decisions)
    client.app.state.v2['dialogue'].adapter_factory=lambda **kw:DialogueAdapter(client=fake,**kw)
    return fake


def decision(action='discover', **kw):
    return DialogueDecision(action=action,reply='Je regarde cela.',intent=SearchIntent(location='Paris',**kw))


def test_real_ideas_do_not_require_common_calendar_and_never_use_demo(client):
    _,a,_=ready(client);source(client,[activity()])
    client.put('/api/v2/availability',headers=headers(a),json={'slots':[]})
    result=turn(client,a,'Une sortie culture à Paris pour quatre-vingts euros')
    assert result['suggestions'][0]['id']=='real_1'
    assert result['plans']==[] and result['intent']['budget']==80
    assert result['diagnostic'] is None and result['mode']=='offline'
    assert all(not s['demo'] for s in result['suggestions'])
    with client.app.state.v2['db'].connect() as c:
        assert c.execute('SELECT count(*) FROM v2_messages').fetchone()[0]==0


def test_old_discover_endpoint_replays_and_closes_the_same_ask_session(client):
    _,a,_=ready(client)
    body={'request_id':'same-request-across-routes','message':''}
    opened=client.post('/api/v2/ask/chat',headers=headers(a),json=body)
    replay=client.post('/api/v2/discover/chat',headers=headers(a),json=body)
    assert opened.status_code==replay.status_code==200
    assert replay.json()=={**opened.json(),'replayed':True}
    closed=client.delete('/api/v2/discover/chat/'+opened.json()['session_id'],headers=headers(a))
    assert closed.status_code==200 and closed.json()=={'closed':True}
    with client.app.state.v2['db'].connect() as c:
        assert c.execute('SELECT count(*) FROM v2_discovery_sessions').fetchone()[0]==0


def test_model_receives_context_corrections_replace_old_constraints_and_no_private_profiles(client,monkeypatch):
    _,a,_=ready(client);source(client,[activity()])
    fake=model(client,monkeypatch,[decision(categories=['culture'],budget=100),decision(categories=['food'],budget=40,preferences=['japanese'],excluded=['culture'])])
    first=turn(client,a,'Une expo à Paris, cent euros pour deux',cloud_consent=True)
    second=turn(client,a,'Finalement japonais, quarante euros, pas de musée',first,cloud_consent=True)
    assert second['intent']['categories']==['food'] and second['intent']['budget']==40
    assert second['suggestions']==[]
    payload=json.loads(fake.calls[2]['input'])
    assert payload['previous_intent']['budget']==100
    assert payload['history'][-1]['role']=='assistant'
    assert 'PRIVATE_ONBOARDING_SENTINEL' not in json.dumps(fake.calls,default=str)
    assert fake.calls[0]['store'] is False and fake.calls[0]['max_output_tokens']==1200
    assert 'correction remplace' in fake.calls[0]['instructions']


def test_no_cloud_without_consent_and_paid_turn_replays_exactly(client,monkeypatch):
    _,a,_=ready(client);source(client,[activity()])
    fake=model(client,monkeypatch,[decision(categories=['culture'])])
    result=turn(client,a,'Une expo à Paris')
    assert not fake.calls and result['mode']=='offline'
    body={'message':'Une expo à Paris','request_id':'same','cloud_consent':True}
    first=client.post('/api/v2/ask/chat',headers=headers(a),json=body).json()
    second=client.post('/api/v2/ask/chat',headers=headers(a),json=body).json()
    assert second['replayed'] and second['session_id']==first['session_id'] and len(fake.calls)==2
    assert client.post('/api/v2/ask/chat',headers=headers(a),json={**body,'message':'Different'}).status_code==409
    quota=client.get('/api/v2/ai/budget',headers=headers(a)).json()
    assert quota['total_reserved']==.04


def test_session_owner_revision_close_and_expiry(client):
    _,a,b=ready(client)
    opened=turn(client,a)
    body={'session_id':opened['session_id'],'revision':opened['revision'],'message':'Paris','request_id':'later'}
    assert client.post('/api/v2/ask/chat',headers=headers(b),json=body).status_code==403
    assert client.delete('/api/v2/ask/chat/'+opened['session_id'],headers=headers(b)).status_code==403
    assert client.post('/api/v2/ask/chat',headers=headers(a),json={**body,'revision':0}).status_code==409
    with client.app.state.v2['db'].connect() as c:
        c.execute('UPDATE v2_discovery_sessions SET expires_at=?',('2000-01-01',))
    assert client.post('/api/v2/ask/chat',headers=headers(a),json=body).status_code==403
    opened=turn(client,a)
    assert client.delete('/api/v2/ask/chat/'+opened['session_id'],headers=headers(a)).json()=={'closed':True}
    with client.app.state.v2['db'].connect() as c:
        assert c.execute('SELECT count(*) FROM v2_discovery_sessions').fetchone()[0]==0


@pytest.mark.parametrize('failure',[TimeoutError('PRIVATE_SECRET'),ValueError('PRIVATE_SECRET'),{'bad':'output'}])
def test_provider_failure_is_visible_and_preserves_turn_for_retry(client,monkeypatch,failure):
    _,a,_=ready(client);source(client,[activity()])
    fake=model(client,monkeypatch,[failure,decision('reply')])
    opened=turn(client,a)
    body={'message':'Une expo à Paris','cloud_consent':True,'request_id':'retry-ai',
          'session_id':opened['session_id'],'revision':opened['revision']}
    response=client.post('/api/v2/ask/chat',headers=headers(a),json=body)
    assert response.status_code==503 and 'PRIVATE_SECRET' not in response.text
    assert response.json()['error']['code'].startswith('provider_')
    with client.app.state.v2['db'].connect() as c:
        row=c.execute('SELECT revision,in_flight,payload FROM v2_discovery_sessions WHERE id=?',(opened['session_id'],)).fetchone()
        assert row['revision']==1 and row['in_flight'] is None
        assert 'Une expo' not in row['payload']
    retry=client.post('/api/v2/ask/chat',headers=headers(a),json=body)
    assert retry.status_code==200 and retry.json()['mode']=='openai' and len(fake.calls)==2


def test_unknown_model_ids_cannot_become_a_plan(client,monkeypatch):
    _,a,_=ready(client);source(client,[activity()])
    model(client,monkeypatch,[decision('plan',selected_ids=['invented'])])
    response=client.post('/api/v2/ask/chat',headers=headers(a),json={
        'message':'Une expo à Paris','cloud_consent':True,'request_id':'unknown-id'})
    assert response.status_code==503 and response.json()['error']['code']=='invalid_selection'


def test_comparing_results_does_not_execute_or_fail_on_an_unused_selection(client,monkeypatch):
    _,a,_=ready(client);source(client,[activity()])
    model(client,monkeypatch,[decision('discover'),decision('reply',selected_ids=['mistyped-id'])])
    first=turn(client,a,'Une expo à Paris',cloud_consent=True)
    compared=turn(client,a,'Explique cette adresse',first,cloud_consent=True)
    assert compared['mode']=='openai' and compared['suggestions']==first['suggestions']
    assert compared['intent']['selected_ids']==[] and compared['plans']==[]


def test_answer_uses_fresh_sources_and_a_second_model_call(client,monkeypatch):
    _,a,_=ready(client);source(client,[activity()])
    fake=model(client,monkeypatch,[decision(categories=['culture'])])
    original=fake.parse
    def explain(**kw):
        response=original(**kw)
        if kw['text_format'] is GroundedReply:
            payload=json.loads(kw['input'])
            assert payload['result']['activities'][0]['id']=='real_1'
            assert payload['result']['activities'][0]['price_per_person']==20
            assert 'person_a_score' not in kw['input'] and 'reasons' not in kw['input']
            response.output_parsed=GroundedReply(candidate_ids=['real_1'],
                reply='Cet atelier de céramique permet de créer quelque chose ensemble. Comptez 40 euros pour deux, à reconfirmer avec le lieu.')
        return response
    fake.parse=explain
    result=turn(client,a,'On voudrait fabriquer quelque chose à deux à Paris',cloud_consent=True)
    assert result['mode']=='openai' and result['reply'].startswith('Cet atelier')
    assert result['suggestions'][0]['id']=='real_1' and result['plans']==[]
    assert len(fake.calls)==2 and all(call['store'] is False for call in fake.calls)
    assert 'PRIVATE_ONBOARDING_SENTINEL' not in json.dumps(fake.calls,default=str)


def test_failed_answer_keeps_real_results_with_a_visible_warning_and_replays(client,monkeypatch):
    _,a,_=ready(client);source(client,[activity()])
    fake=model(client,monkeypatch,[decision()])
    original=fake.parse
    def invented(**kw):
        response=original(**kw)
        if kw['text_format'] is GroundedReply:
            response.output_parsed=GroundedReply(candidate_ids=['invented'],reply='PRIVATE_INVALID_ANSWER')
        return response
    fake.parse=invented
    body={'message':'Une expo à Paris','cloud_consent':True,'request_id':'bad-answer'}
    result=client.post('/api/v2/ask/chat',headers=headers(a),json=body).json()
    assert result['mode']=='openai_partial' and result['warning']
    assert result['suggestions'][0]['id']=='real_1'
    assert 'PRIVATE_INVALID_ANSWER' not in json.dumps(result)
    replay=client.post('/api/v2/ask/chat',headers=headers(a),json=body).json()
    assert replay=={**result,'replayed':True} and len(fake.calls)==2


def test_disabled_ai_is_visible_in_ask_while_discover_stays_available(client,monkeypatch):
    _,a,_=ready(client);source(client,[activity()])
    fake=model(client,monkeypatch,[])
    monkeypatch.setenv('OPENAI_ENABLED','0')
    response=client.post('/api/v2/ask/chat',headers=headers(a),json={
        'message':'Une expo à Paris','cloud_consent':True,'request_id':'ai-disabled'})
    assert response.status_code==503
    assert response.json()['error']['code']=='not_configured_or_disabled'
    assert not fake.calls
    with client.app.state.v2['db'].connect() as c:
        assert c.execute('SELECT count(*) FROM v2_discovery_sessions').fetchone()[0]==0
    assert client.get('/api/v2/activities/real',headers=headers(a)).json()['items']


def test_real_source_filters_expired_budget_location_and_exclusions(client):
    pair,a,_=ready(client)
    old=activity('old',start='2020-01-01T18:00:00+01:00',end='2020-01-01T19:00:00+01:00')
    source(client,[old,activity('expensive',price_per_person=100),activity('unknown',price_per_person=None),activity()])
    real=client.app.state.v2['real_recommendations']
    found=real.search(pair['couple_id'],SearchIntent(location='Paris',budget=50))
    assert {a['id'] for a in found['items']}=={'real_1','unknown'}
    assert 'Prix inconnu' in next(a for a in found['items'] if a['id']=='unknown')['unknown']
    assert real.search(pair['couple_id'],SearchIntent(location='Lille'))['items']==[]
    assert real.search(pair['couple_id'],SearchIntent(excluded=['culture']))['items']==[]


def test_other_ideas_exclude_previous_results_and_conversation_exceeds_three_turns(client):
    _,a,_=ready(client);source(client,[activity(str(i)) for i in range(6)])
    first=turn(client,a,'Une expo à Paris')
    second=turn(client,a,'Autres idées',first)
    assert set(a['id'] for a in first['suggestions']).isdisjoint(a['id'] for a in second['suggestions'])
    current=second
    for _ in range(10):current=turn(client,a,'Pourquoi cette idée ?',current)
    assert current['revision']==12 and current['plans']==[]


def test_web_reuses_existing_connector_only_with_separate_consent(client,monkeypatch):
    _,a,_=ready(client);source(client,[])
    model(client,monkeypatch,[decision('web'),decision('web')])
    calls=[]
    def search(member,body):
        calls.append(body)
        return {'status':'completed','answer':'Une exposition documentée.',
                'activities':[{'name':'Expo sourcée','category':'culture','kind':'place',
                    'source_url':'https://example.org','description':'Une exposition documentée.',
                    'address':'Paris','price':10,'price_unit':'person','tags':[]}],
                'sources':[{'url':'https://example.org','title':'Source'}],'segments':[],'cached':False}
    client.app.state.v2['dialogue'].web=SimpleNamespace(search=search)
    result=turn(client,a,'Cherche une expo à Paris',cloud_consent=True)
    assert not calls and 'web' not in result
    result=turn(client,a,'Cherche sur le web',result,cloud_consent=True,web_consent=True)
    assert len(calls)==2 and calls[1].refinement and result['web']['sources'] and 'disponibilité' in result['reply']
    assert 'PRIVATE_ONBOARDING' not in calls[0].text
    assert client.post('/api/v2/ask/chat',headers=headers(a),json={'request_id':'bad-consent','web_consent':True}).status_code==422


def test_program_requires_complete_real_data_not_fake_calendar_reason(client,monkeypatch):
    _,a,_=ready(client);source(client,[activity(price_per_person=None)])
    model(client,monkeypatch,[decision('plan',start='2090-10-02T18:00:00+02:00',end='2090-10-02T23:00:00+02:00')])
    result=turn(client,a,'Organise le programme',cloud_consent=True)
    assert result['diagnostic']['code']=='activity_details_missing'
    assert result['plans']==[]


def test_actual_real_program_saved_and_retry_does_not_duplicate(client,monkeypatch):
    pair,a,b=ready(client);event=activity();source(client,[event])
    # This scenario has no travel-to-origin constraint; no origin is invented.
    memory=client.app.state.v2['memory']
    for person in [a,b]:
        for f in memory.list_facts(pair['couple_id'],'PERSON',person['id'],person['id']):
            if f['category']=='practical':memory.delete(f['id'],person['id'])
    start=datetime.fromisoformat(event['start'])-timedelta(hours=1)
    end=datetime.fromisoformat(event['end'])+timedelta(hours=1)
    model(client,monkeypatch,[decision('plan',categories=['culture'],start=start.isoformat(),end=end.isoformat(),budget=80)])
    body={'message':'Fais un programme','cloud_consent':True,'request_id':'plan-once'}
    response=client.post('/api/v2/ask/chat',headers=headers(a),json=body)
    assert response.status_code==200,response.text
    result=response.json()
    assert result['plans'],result
    plan=result['plans'][0]
    assert plan['source']=='real_source_availability_unconfirmed' and plan['activities'][0]['demo'] is False
    assert plan['activities'][0]['id']=='real_1' and plan['total_couple_cost']==40
    again=client.post('/api/v2/ask/chat',headers=headers(a),json=body).json()
    assert again['plans'][0]['id']==plan['id']
    assert client.get('/api/v2/date-plans/'+plan['id'],headers=headers(b)).status_code==200
    assert len(client.get('/api/v2/date-plans',headers=headers(a)).json()['items'])==1


def planning_error(client, cid, **extra):
    from backend.streams.E_orchestrator.service import Query, PlanningIssue
    # Card searches no longer require a common calendar. Explicit voice
    # composition still validates availability before using its candidates.
    with pytest.raises(PlanningIssue) as caught:
        client.app.state.v2['planning'].query(cid, Query(text='Une balade', **extra),
            candidate_provider=lambda window, budget: [])
    return caught.value.code


def test_calendar_error_codes_are_distinct_from_no_catalog_result(client):
    pair,a,b=ready(client)
    client.put('/api/v2/availability',headers=headers(a),json={'slots':[]})
    assert planning_error(client,pair['couple_id'])=='calendar_incomplete'
    client.put('/api/v2/availability',headers=headers(b),json={'slots':[]})
    assert planning_error(client,pair['couple_id'])=='calendar_empty'
    response=client.post('/api/v2/recommendations/query',headers=headers(a),json={'text':'Une balade'})
    assert response.status_code==200  # Ideas remain accessible without scheduling.


@pytest.mark.parametrize('text,total',[('quatre-vingts euros',80),('cent vingt euros',120),('quarante euros chacun',80),('soixante-dix euros',70)])
def test_spoken_amounts(text,total):
    assert spoken_budget(text)==total


def test_calendar_expired_no_overlap_and_requested_window_are_distinct(client):
    pair,a,b=ready(client)
    def save(person,start,end):
        assert client.put('/api/v2/availability',headers=headers(person),json={'slots':[{'start':start,'end':end}]}).status_code==200
    def code(**extra):
        return planning_error(client,pair['couple_id'],**extra)
    save(a,'2090-01-01T18:00:00+01:00','2090-01-01T22:00:00+01:00')
    save(b,'2090-01-02T18:00:00+01:00','2090-01-02T22:00:00+01:00')
    assert code()=='calendar_no_overlap'
    save(b,'2090-01-01T18:00:00+01:00','2090-01-01T22:00:00+01:00')
    assert code(time_window={'start':'2090-01-02T18:00:00+01:00','end':'2090-01-02T22:00:00+01:00'})=='requested_time_unavailable'
    for person in [a,b]:save(person,'2020-01-01T18:00:00+01:00','2020-01-01T22:00:00+01:00')
    assert code()=='calendar_expired'


def test_dates_without_hours_filter_events_and_malformed_dates_never_crash(client,monkeypatch):
    _,a,_=ready(client);event=activity();source(client,[event])
    day=datetime.fromisoformat(event['start']).date().isoformat()
    model(client,monkeypatch,[decision(date_from=day,date_to=day),decision(date_from='2090-99-99'),decision(start='not-a-date',end='tomorrow')])
    first=turn(client,a,'Une expo ce jour-là à Paris',cloud_consent=True)
    assert first['suggestions']
    second=turn(client,a,'Une autre date',first,cloud_consent=True)
    assert second['diagnostic']['code']=='invalid_date'
    third=turn(client,a,'Un créneau',second,cloud_consent=True)
    assert third['diagnostic']['code']=='invalid_time'


def test_openai_quota_exhaustion_is_explicit_and_does_not_call_sdk(client,monkeypatch):
    _,a,_=ready(client);source(client,[activity()])
    fake=model(client,monkeypatch,[decision()]);monkeypatch.setenv('OPENAI_DAILY_RESERVE_USD','0')
    response=client.post('/api/v2/ask/chat',headers=headers(a),json={
        'message':'Une expo à Paris','cloud_consent':True,'request_id':'quota'})
    assert response.status_code==503 and response.json()['error']['code']=='budget_limit_reached'
    assert not fake.calls


def test_in_flight_request_is_not_duplicated_and_close_cannot_resurrect_it(client,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    _,a,_=ready(client);source(client,[activity()]);opened=turn(client,a)
    entered,release=Event(),Event()
    fake=model(client,monkeypatch,[decision()])
    original=fake.parse
    def waiting(**kw):
        entered.set();assert release.wait(5)
        return original(**kw)
    fake.parse=waiting
    body={'message':'Une expo à Paris','cloud_consent':True,'request_id':'in-flight','session_id':opened['session_id'],'revision':opened['revision']}
    with ThreadPoolExecutor() as executor:
        pending=executor.submit(client.post,'/api/v2/ask/chat',headers=headers(a),json=body)
        assert entered.wait(5)
        try:
            assert client.post('/api/v2/ask/chat',headers=headers(a),json=body).status_code==409
            assert client.delete('/api/v2/ask/chat/'+opened['session_id'],headers=headers(a)).status_code==200
        finally:release.set()
        assert pending.result().status_code==403
    with client.app.state.v2['db'].connect() as c:
        assert c.execute('SELECT count(*) FROM v2_discovery_sessions').fetchone()[0]==0
    assert len(fake.calls)==1


def test_personal_erasure_removes_discovery_sessions_but_not_partner(client):
    _,a,b=ready(client)
    turn(client,a,'Une expo à Paris');turn(client,b,'Un restaurant à Paris')
    response=client.request('DELETE','/api/v2/users/me/data',headers=headers(a),json={'confirmation':'DELETE MY DATA'})
    assert response.status_code==200,response.text
    with client.app.state.v2['db'].connect() as c:
        assert [r[0] for r in c.execute('SELECT owner_id FROM v2_discovery_sessions')]==[b['id']]


def test_private_partner_facts_never_enter_model_and_consented_exclusions_filter_locally(client,monkeypatch):
    couple,a,b=ready(client);source(client,[activity()])
    memory=client.app.state.v2['memory']
    memory.ingest(couple['couple_id'],'PERSON',b['id'],b['id'],'interests','secret',{'values':['PARTNER_PRIVATE_SENTINEL']},'PRIVATE')
    memory.ingest(couple['couple_id'],'PERSON',b['id'],b['id'],'dislikes','refusal',{'values':['culture']},'COUPLE_RECOMMENDATION')
    fake=model(client,monkeypatch,[decision(categories=['culture'])])
    result=turn(client,a,'Une expo à Paris',cloud_consent=True)
    assert result['suggestions']==[]
    assert 'PARTNER_PRIVATE_SENTINEL' not in json.dumps(fake.calls,default=str)
    assert 'refusal' not in fake.calls[0]['input']


def test_multiweek_event_cannot_be_scheduled_as_one_very_long_session(client):
    pair,_,_=ready(client)
    a=activity();a['end']=(datetime.fromisoformat(a['start'])+timedelta(days=25)).isoformat();source(client,[a])
    real=client.app.state.v2['real_recommendations']
    from backend.streams.E_orchestrator.models import TimeWindow
    window=TimeWindow(start=a['start'],end=(datetime.fromisoformat(a['start'])+timedelta(hours=5)).isoformat())
    assert real.search(pair['couple_id'],SearchIntent(location='Paris'))['items']
    assert real.candidates(pair['couple_id'],SearchIntent(location='Paris'),window,150)==[]


def test_requested_specific_taste_survives_real_candidate_to_planner_ranking(client):
    from backend.streams.E_orchestrator.models import TimeWindow, CandidateActivity, CoupleProfile, PlanRequest
    from backend.streams.E_orchestrator.planner import generate
    pair,a,b=ready(client)
    memory=client.app.state.v2['memory']
    for person in [a,b]:
        for fact in memory.list_facts(pair['couple_id'],'PERSON',person['id'],person['id']):
            if fact['category']=='practical':memory.delete(fact['id'],person['id'])
    sushi=activity('z_sushi',type='food',name='Dîner japonais test',tags=['japanese'])
    pizza=activity('a_pizza',type='food',name='Dîner italien test',tags=['italian'])
    source(client,[pizza,sushi]);real=client.app.state.v2['real_recommendations']
    intent=SearchIntent(location='Paris',categories=['food'],preferences=['japanese'])
    from backend.streams.A_calendar.service import paris_window
    window=paris_window(TimeWindow(start=sushi['start'],end=sushi['end']))
    candidates=real.candidates(pair['couple_id'],intent,window,100)
    plans,_=generate(PlanRequest(time_window=window,couple_profile=CoupleProfile(typical_budget=100),candidate_activities=[CandidateActivity(**row['candidate']) for row in candidates],max_plans=1),max_activities=1)
    assert plans[0].activities[0].id=='z_sushi'


@pytest.mark.parametrize('cleared', [{'values': []}, {'skip': True}])
def test_only_actual_onboarding_exclusions_filter_japanese_recommendations(client, cleared):
    from backend.tests.test_api import create, answer
    couple = create(client)
    cid = couple['couple_id']
    a, b = couple['members']
    for member in (a, b):
        for step in range(1, 8):
            value = {'name': member['name']} if step == 1 else {'skip': True}
            assert answer(client, couple, member, step, value).status_code == 200
        response = client.post(f'/api/v2/onboarding/couples/{cid}/members/{member["id"]}/complete',
                               headers=headers(member))
        assert response.status_code == 200
    source(client, [activity('japanese-test', name='Restaurant japonais test', type='restaurant',
                            description='Cuisine japonaise', tags=['japonais', 'food'])])
    recommendations = client.app.state.v2['real_recommendations']
    intent = SearchIntent(location='Paris', categories=['food'], preferences=['japonais'])
    result = recommendations.search(cid, intent)
    assert [row['id'] for row in result['items']] == ['japanese-test']
    assert result['budget_cap'] is None  # Skipping does not invent a budget.
    # Each person's own form controls their restrictions; a different couple's
    # responses must never leak into this couple's recommendations.
    other = create(client)
    assert answer(client, other, other['members'][0], 3, {'values': ['japonais']}).status_code == 200
    assert recommendations.search(cid, intent)['total'] == 1
    assert answer(client, couple, b, 3, {'values': ['japonais']}).status_code == 200
    assert recommendations.search(cid, intent)['total'] == 0
    # Editing or skipping the earlier answer supersedes it, including after reload.
    assert answer(client, couple, b, 3, cleared).status_code == 200
    assert recommendations.search(cid, intent)['total'] == 1
    from backend.api.app import create_app
    reopened = create_app(client.app.state.v2['db'].path)
    reopened.state.v2['real_recommendations'].source = recommendations.source
    assert reopened.state.v2['real_recommendations'].search(cid, intent)['total'] == 1
    facts = reopened.state.v2['memory'].list_facts(cid, 'PERSON', b['id'], b['id'])
    assert {fact['source'] for fact in facts} == {'onboarding'}
    refusals = [fact for fact in facts if fact['key'] == 'onboarding:3']
    assert len(refusals) == 1 and refusals[0]['value'] == cleared
