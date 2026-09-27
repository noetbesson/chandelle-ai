"""Behavioral regression contracts for the two-project integration; no network."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from backend.tests.test_api import client, offline_only, ready, headers, query, PREFIX
from backend.streams.A_calendar.service import instant, intersect
from backend.streams.F_booking.service import calendar
from backend.integrations.urls import public_url
from backend.streams.H_conversation.service import parse_request
from backend.streams.D_connectors.service import SignalImport, parse_import


@pytest.mark.parametrize('text,budget,categories,excluded',[
    ('Un restaurant japonais à 40 € chacun',80,['food'],[]),
    ('Cinéma à moins de 25 euros pour deux',25,['cinema'],[]),
    ('Une expo sans cinéma',None,['culture'],['cinema']),
    ('food under 40 no cinema',40,['food'],['cinema']),
    ('Un atelier à 12,50 € par personne',25,['workshops'],[]),
])
def test_bilingual_request(text,budget,categories,excluded):
    assert parse_request(text)=={'budget':budget,'categories':categories,'excluded':excluded}


@pytest.mark.parametrize('value',['2026-03-29T02:30:00','2026-10-25T02:30:00'])
def test_paris_rejects_nonexistent_or_ambiguous_local_time(value):
    with pytest.raises(ValueError):instant(value)


def test_offsets_and_adjacent_intersections():
    assert instant('2026-09-26T19:00:00').isoformat()=='2026-09-26T17:00:00+00:00'
    assert instant('2026-10-25T02:30:00+02:00')!=instant('2026-10-25T02:30:00+01:00')
    t=lambda m:instant(f'2026-09-26T19:{m:02}:00')
    assert intersect([(t(0),t(20)),(t(20),t(40))],[(t(0),t(40))])==[(t(0),t(40))]


def test_manual_calendar_scopes_planning_and_persists(client):
    couple,a,b=ready(client)
    assert client.get(PREFIX+'/availability',headers=headers(a)).json()['mode']=='demo'
    def put(person,start,end):
        return client.put(PREFIX+'/availability',headers=headers(person),json={'slots':[{'start':start,'end':end}]})
    assert put(a,'2026-09-26T18:00:00','2026-09-26T20:30:00').status_code==200
    blocked=client.post(PREFIX+'/recommendations/query',headers=headers(a),json={'text':'A date'})
    assert blocked.status_code==200 and blocked.json()['plans']==[] and blocked.json()['warnings']
    assert not client.post(PREFIX+'/suggestions/check',headers=headers(a)).json()['triggered']
    assert put(b,'2026-09-26T19:00:00','2026-09-26T23:00:00').status_code==200
    state=client.get(PREFIX+'/availability',headers=headers(a)).json()
    assert len(state['own_slots'])==1
    assert state['common_slots']==[{'start':'2026-09-26T17:00:00+00:00','end':'2026-09-26T18:30:00+00:00'}]
    assert '2026-09-26T21:00:00+00:00' not in json.dumps(state)  # partner's private end
    plan=query(client,a,activity_count=1)['plans'][0]
    assert instant(plan['start'])>=instant(state['common_slots'][0]['start'])
    assert instant(plan['end'])<=instant(state['common_slots'][0]['end'])
    from backend.streams.A_calendar.service import AvailabilityService
    from backend.db import Database
    assert AvailabilityService(Database(client.app.state.v2['db'].path)).state(couple['couple_id'],a['id'])==state


def test_planning_tries_later_feasible_common_slot(client):
    _,a,b=ready(client)
    slots=[{'start':'2026-09-26T17:00:00','end':'2026-09-26T18:00:00'},
           {'start':'2026-09-26T19:00:00','end':'2026-09-26T23:00:00'}]
    for person in (a,b):
        assert client.put(PREFIX+'/availability',headers=headers(person),json={'slots':slots}).status_code==200
    result=query(client,a,time_window={'start':'2026-09-26T16:00:00','end':'2026-09-26T23:00:00'})
    assert result['plans']


@pytest.mark.parametrize('url', ['javascript:alert(1)','https://localhost/a','http://127.0.0.1/a','http://10.0.0.2/a','http://[::1]/','https://user:pass@example.org','https://example.org/x\nBEGIN:VEVENT'])
def test_unsafe_urls_are_not_handoffs(url):
    assert public_url(url) is None


def test_inert_link_and_tracking_deduplication():
    first=parse_import(SignalImport(platform='instagram',content='https://www.instagram.com/p/jazz/?utm_source=share'))
    second=parse_import(SignalImport(platform='instagram',content='https://instagram.com/p/jazz/'))
    assert first['entries'][0]['fingerprint']==second['entries'][0]['fingerprint']
    assert first['entries'][0]['proposed_tags']==[]
    assert first['entries'][0]['signal_at'] is None
    assert first['warnings']


@pytest.mark.parametrize('platform,format,content,expected',[
    ('google_maps','csv','Title,URL,Note\nJazz café,https://example.org/place,"Une soirée jazz, au calme"','jazz'),
    ('google_maps','json',json.dumps({'type':'FeatureCollection','features':[{'properties':{'Location':{'Business Name':'Musée de la peinture'},'Google Maps URL':'https://example.org/museum'}}]}),'culture'),
    ('instagram','json',json.dumps({'saved_saved_media':[{'caption':'Un atelier céramique','string_map_data':{'Saved on':{'href':'https://instagram.com/p/1','timestamp':1700000000}}}]}),'creative'),
    ('tiktok','json',json.dumps({'Activity':{'Favorite Videos':[{'Link':'https://tiktok.com/video/1','Description':'Un concert jazz','Date':'2026-09-20'}]}}),'jazz'),
])
def test_recognized_exports(platform,format,content,expected):
    result=parse_import(SignalImport(platform=platform,format=format,content=content))
    assert len(result['entries'])==1
    assert expected in result['entries'][0]['proposed_tags']


def test_negated_import_never_becomes_a_like():
    entry=parse_import(SignalImport(content='Je déteste le jazz mais j’adore le cinéma.'))['entries'][0]
    assert 'jazz' not in entry['proposed_tags']
    assert 'cinema' in entry['proposed_tags']


def test_inspiration_confirmation_consent_dedup_revoke_and_expiry(client):
    couple,a,b=ready(client)
    memory=client.app.state.v2['memory']
    payload={'content':'J’adore le jazz. SENTINEL_IMPORT','privacy_scope':'COUPLE_RECOMMENDATION'}
    result=client.post(PREFIX+'/inspirations/import',headers=headers(a),json=payload)
    assert result.status_code==200,result.text
    fact=result.json()['items'][0]
    assert 'jazz' not in memory.planning_context(couple['couple_id'])['person_a']['interests']
    assert client.get(PREFIX+'/inspirations',headers=headers(b)).json()['items']==[]
    assert client.post(PREFIX+'/inspirations/'+fact['id']+'/confirm',headers=headers(b),json={'tags':['jazz']}).status_code==403
    confirmation={'tags':['jazz'],'privacy_scope':'COUPLE_RECOMMENDATION','horizon':'durable'}
    confirmed=client.post(PREFIX+'/inspirations/'+fact['id']+'/confirm',headers=headers(a),json=confirmation).json()
    assert confirmed['source']=='inspiration_import'
    assert 'jazz' in memory.planning_context(couple['couple_id'])['person_a']['interests']
    assert 'SENTINEL_IMPORT' not in client.get(PREFIX+f"/couples/{couple['couple_id']}/profile",headers=headers(b)).text
    duplicate=client.post(PREFIX+'/inspirations/import',headers=headers(a),json=payload).json()
    assert duplicate['duplicates']==1 and duplicate['items'][0]['id']==confirmed['id']
    assert len(client.get(PREFIX+'/inspirations',headers=headers(a)).json()['items'])==1
    revoked=client.post(PREFIX+'/memories/'+confirmed['id']+'/share',headers=headers(a),json={'privacy_scope':'PRIVATE'})
    assert revoked.status_code==200
    assert 'jazz' not in memory.planning_context(couple['couple_id'])['person_a']['interests']
    old=(datetime.now(timezone.utc)-timedelta(days=90)).isoformat()
    fact=client.post(PREFIX+'/inspirations/import',headers=headers(a),json={'content':'J’aime la céramique','signal_at':old}).json()['items'][0]
    expired=client.post(PREFIX+'/inspirations/'+fact['id']+'/confirm',headers=headers(a),json={**confirmation,'tags':['creative'],'horizon':'temporary'})
    assert expired.status_code==200,expired.text
    assert 'creative' not in memory.planning_context(couple['couple_id'])['person_a']['interests']


def test_web_comparison_selected_composition_and_unknown_prices(client):
    _,a,b=ready(client)
    result=query(client,a)
    selected=[v['id'] for v in result['plans'][0]['activities']]
    compared=client.post(PREFIX+'/activities/compare',headers=headers(a),json={'activity_ids':selected}).json()
    assert compared['budget_complete'] and compared['total_couple_cost']==result['plans'][0]['total_couple_cost']
    assert client.get(PREFIX+'/activities?limit=100',headers=headers(a)).json()['total']==0
    result=query(client,a,required_activity_ids=selected)
    assert result['plans'] and all(set(selected)=={x['id'] for x in p['activities']} for p in result['plans'])


def test_booking_and_calendar_require_acceptance_and_couple_membership(client):
    _,a,b=ready(client)
    plan=query(client,a)['plans'][0]
    base=PREFIX+'/date-plans/'+plan['id']
    assert client.post(base+'/booking',headers=headers(a)).status_code==422
    assert client.get(base+'/calendar',headers=headers(a)).status_code==422
    assert client.patch(base,headers=headers(a),json={'status':'accepted'}).status_code==200
    prepared=client.post(base+'/booking',headers=headers(b)).json()
    assert prepared['payment_performed'] is False
    assert all(x['requires_user_confirmation'] for x in prepared['actions'])
    exported=client.get(base+'/calendar',headers=headers(a))
    assert exported.status_code==200
    assert 'DTSTART:20260926T170000Z' in exported.text
    assert exported.text.count('BEGIN:VEVENT')==2
    assert 'Cache-Control' in exported.headers
    _,outsider,_=ready(client)
    assert client.get(base+'/calendar',headers=headers(outsider)).status_code==404
    assert client.post(base+'/booking',headers=headers(outsider)).status_code==404
    assert client.get(base+'/calendar').status_code==403


def test_ics_utf8_folding_and_injection_escaping(client):
    _,a,_=ready(client)
    plan=query(client,a)['plans'][0]
    plan['status']='accepted'
    plan['activities'][0]['title']='é'*100+'\r\nBEGIN:VEVENT'
    text=calendar(plan)
    assert all(len(line.encode())<=75 for line in text.split('\r\n'))
    assert text.count('\r\nBEGIN:VEVENT\r\n')==len(plan['activities'])
    assert '\\nBEGIN:VEVENT' in text.replace('\r\n ','')


def test_personal_erasure_covers_imports_and_calendar(client):
    _,a,b=ready(client)
    for person in (a,b):
        assert client.post(PREFIX+'/inspirations/import',headers=headers(person),json={'content':'J’aime le jazz'}).status_code==200
        assert client.put(PREFIX+'/availability',headers=headers(person),json={'slots':[]}).status_code==200
    assert client.request('DELETE',PREFIX+'/users/me/data',headers=headers(a),json={'confirmation':'DELETE MY DATA'}).status_code==200
    with client.app.state.v2['db'].connect() as con:
        assert con.execute('SELECT COUNT(*) FROM v2_availability WHERE user_id=?',(a['id'],)).fetchone()[0]==0
        assert con.execute('SELECT COUNT(*) FROM v2_availability WHERE user_id=?',(b['id'],)).fetchone()[0]==1
        assert con.execute('SELECT COUNT(*) FROM v2_facts WHERE owner_id=?',(a['id'],)).fetchone()[0]==0


def test_temporary_preference_weight_does_not_accumulate_or_churn_snapshots(client):
    couple,a,_=ready(client)
    source=(datetime.now(timezone.utc)-timedelta(days=20)).isoformat()
    for content in ('Du jazz ce mois-ci','Une autre idée jazz'):
        imported=client.post(PREFIX+'/inspirations/import',headers=headers(a),json={'content':content,'signal_at':source}).json()['items'][0]
        result=client.post(PREFIX+'/inspirations/'+imported['id']+'/confirm',headers=headers(a),json={'tags':['jazz'],'privacy_scope':'COUPLE_RECOMMENDATION','horizon':'temporary'})
        assert result.status_code==200
    memory=client.app.state.v2['memory']
    profile=memory.planning_context(couple['couple_id'])['person_a']
    assert .5<profile['interest_weights']['jazz']<.52
    first=memory.profile(couple['couple_id'],'PERSON',a['id'],a['id'])
    second=memory.profile(couple['couple_id'],'PERSON',a['id'],a['id'])
    assert first['version']==second['version']


def test_calendar_change_expires_pending_suggestions(client):
    _,a,_=ready(client)
    suggestion=client.post(PREFIX+'/suggestions/check',headers=headers(a)).json()
    assert suggestion['triggered']
    assert client.put(PREFIX+'/availability',headers=headers(a),json={'slots':[]}).status_code==200
    feed=client.get(PREFIX+'/suggestions',headers=headers(a)).json()['items']
    assert next(s for s in feed if s['id']==suggestion['id'])['state']=='expired'


@pytest.mark.parametrize('payload',[
    {'platform':'manual','format':'json','content':'{}'},
    {'platform':'google_maps','format':'csv','content':'Title,Note\nhello,world'},
    {'platform':'tiktok','format':'json','content':'{"Direct Messages":[{"Link":"https://example.org"}]}'},
    {'platform':'instagram','format':'json','content':'{invalid'},
])
def test_invalid_imports_return_validation_envelopes(client,payload):
    _,a,_=ready(client)
    response=client.post(PREFIX+'/inspirations/import',headers=headers(a),json=payload)
    assert response.status_code==422
    assert 'error' in response.json()
