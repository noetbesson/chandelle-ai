"""Real API/SQLite integration with fake calendar providers; no external accounts are touched."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import MagicMock
from cryptography.fernet import Fernet
import pytest
from backend.tests.test_api import client, offline_only, ready, headers, query, PREFIX
from backend.integrations.calendar.provider import CalendarError, TimeSlot, CalendarEvent
from backend.integrations.calendar.store import CalendarStore
from backend.integrations.calendar.google import GoogleCalendar
from backend.integrations.calendar.outlook import OutlookCalendar
from backend.api.calendar import CallbackLogFilter
from backend.streams.A_calendar.service import AvailabilityInput, AvailabilityService, instant
from backend.streams.A_calendar.calendar_read import subtract_busy
from backend.streams.G_proactive.mood_tracker import MoodTracker, MoodSignal, compute_opportunity_score

UTC=timezone.utc

@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setenv('CALENDAR_TOKEN_KEY',Fernet.generate_key().decode())
    monkeypatch.setenv('PROACTIVE_SCHEDULER_ENABLED','0')
    monkeypatch.delenv('GOOGLE_CLIENT_ID',raising=False)
    monkeypatch.delenv('MICROSOFT_CLIENT_ID',raising=False)

class FakeCalendar:
    def __init__(self,busy=()):self.busy=list(busy);self.calls=[];self.fail=False
    def get_busy_slots(self,start,end):
        if self.fail:raise RuntimeError('SECRET MUST NOT LEAK')
        return self.busy
    def create_event(self,event,key):
        self.calls.append(('create',key))
        if self.fail:raise RuntimeError('SECRET MUST NOT LEAK')
        return 'remote-'+key
    def update_event(self,eid,event):self.calls.append(('update',eid));return True
    def delete_event(self,eid):self.calls.append(('delete',eid));return True

def identities(client):
    client.base_url='http://localhost:8000'
    couple,a,b=ready(client)
    return couple,{**a,'couple_id':couple['couple_id']},{**b,'couple_id':couple['couple_id']}

def setup_slots(client,couple,a,b):
    start=(datetime.now(UTC)+timedelta(days=1)).replace(hour=16,minute=0,second=0,microsecond=0)
    end=start+timedelta(hours=5)
    for m in (a,b):
        response=client.put(PREFIX+'/availability',headers=headers(m),json={'slots':[{'start':start.isoformat(),'end':end.isoformat()}]})
        assert response.status_code==200,response.text
    return start,end

def test_tokens_encrypted_and_member_endpoints_isolated(client):
    couple,a,b=identities(client);store=client.app.state.calendars['store']
    store.save(a['id'],'google',{'refresh_token':'SECRET-TOKEN'})
    with store.db.connect() as c:raw=c.execute('SELECT credentials FROM v2_calendar_connections').fetchone()[0]
    assert 'SECRET-TOKEN' not in raw and store.open(raw)['refresh_token']=='SECRET-TOKEN'
    status=client.get(PREFIX+'/calendar/status',headers=headers(a))
    assert status.json()['connected'] and 'SECRET' not in status.text
    assert not client.get(PREFIX+'/calendar/status',headers=headers(b)).json()['connected']
    assert client.get(PREFIX+'/calendar/status').status_code in (401,403)
    assert client.post('/api/proactive/trigger/foreign',headers=headers(a),json={}).status_code==403
    assert client.post(PREFIX+'/calendar/plans/foreign/confirm',headers=headers(a),json={'revision':'a'*64}).status_code==404

def test_missing_config_and_bad_key_block_oauth(client,monkeypatch):
    _,a,_=identities(client)
    r=client.get('/api/calendar/connect/google',headers=headers(a))
    assert r.status_code==422 and 'not_configured' in r.text
    monkeypatch.setenv('CALENDAR_TOKEN_KEY','broken')
    with pytest.raises(CalendarError):CalendarStore(client.app.state.v2['db']).save(a['id'],'google',{})

def test_google_pkce_state_cookie_replay_and_exchange(client,monkeypatch):
    _,a,_=identities(client)
    monkeypatch.setenv('GOOGLE_CLIENT_ID','test-id');monkeypatch.setenv('GOOGLE_CLIENT_SECRET','test-secret')
    r=client.get('/api/calendar/connect/google?format=json',headers=headers(a))
    assert r.status_code==200,r.text
    parsed=parse_qs(urlsplit(r.json()['authorization_url']).query)
    assert parsed['code_challenge_method']==['S256'] and parsed['access_type']==['offline']
    assert 'httponly' in r.headers['set-cookie'].lower()
    fake=SimpleNamespace(fetch_token=lambda **kw:None,credentials=SimpleNamespace(to_json=lambda:json.dumps({'refresh_token':'private'})))
    monkeypatch.setattr('backend.integrations.calendar.calendar_auth.google_flow',lambda *args:fake)
    state=parsed['state'][0]
    bad=client.get('/api/calendar/callback/google?state=bad&code=fake',follow_redirects=False)
    assert bad.headers['location'].endswith('failed')
    # Begin again after the failed callback clears the browser binding.
    client.cookies.set('chandelle_calendar_oauth',hashlib.sha256(state.encode()).hexdigest(),path='/api/calendar/callback')
    r=client.get('/api/calendar/callback/google',params={'state':state,'code':'fake'},follow_redirects=False)
    assert r.headers['location'].endswith('connected'),r.text
    assert client.app.state.calendars['store'].status(a['id'])['connected']
    with pytest.raises(CalendarError):client.app.state.calendars['auth'].finish('google',{'state':state,'code':'fake'})

def test_callback_logs_drop_authorization_query():
    record=logging.LogRecord('uvicorn.access',20,'',1,'%s %s %s %s %s',('ip','GET','/api/calendar/callback/google?code=SECRET&state=PRIVATE','1.1',303),None)
    CallbackLogFilter().filter(record)
    assert 'SECRET' not in record.getMessage() and 'PRIVATE' not in record.getMessage()

def test_intersections_refresh_fail_closed_and_requested_slot_no_bypass(client):
    couple,a,b=identities(client);start,end=setup_slots(client,couple,a,b)
    services=client.app.state.calendars
    providers={a['id']:FakeCalendar([TimeSlot(start=start,end=start+timedelta(hours=1))]),b['id']:FakeCalendar([TimeSlot(start=end-timedelta(hours=1),end=end)])}
    for m in (a,b):services['store'].save(m['id'],'google',{})
    services['read'].provider_factory=lambda uid:providers[uid]
    slots=services['read'].find_common_free_slots(a['id'],b['id'],start,end,120)
    assert len(slots)==1 and slots[0].start==start+timedelta(hours=1) and slots[0].end==end-timedelta(hours=1)
    assert services['read'].cached_common(couple['couple_id'])
    providers[a['id']].fail=True
    with pytest.raises(CalendarError):services['read'].refresh(a['id'])
    assert not services['read'].cached_common(couple['couple_id'])
    with pytest.raises(ValueError):AvailabilityService(services['read'].db).windows(couple['couple_id'],TimeSlot(start=start,end=end))
    with services['read'].db.connect() as c:assert c.execute('SELECT busy FROM v2_calendar_connections WHERE user_id=?',(a['id'],)).fetchone()[0]

def test_disconnected_partner_not_free_and_expired_cache_not_used(client):
    couple,a,b=identities(client);svc=client.app.state.calendars;start=datetime.now(UTC);end=start+timedelta(days=7)
    svc['store'].save(a['id'],'google',{});svc['read'].provider_factory=lambda _:FakeCalendar()
    assert not svc['read'].find_common_free_slots(a['id'],b['id'],start,end)
    with pytest.raises(PermissionError):svc['read'].find_common_free_slots(a['id'],a['id'],start,end)
    with pytest.raises(CalendarError):svc['read'].find_common_free_slots(a['id'],b['id'],start,end+timedelta(days=15))

def test_both_confirm_retry_partial_update_cancel_and_revision(client,monkeypatch):
    couple,a,b=identities(client)
    p=query(client,a)['plans'][0];pid=p['id']
    planning=client.app.state.v2['planning'];planning.change(couple['couple_id'],pid,'accepted')
    svc=client.app.state.calendars;providers={a['id']:FakeCalendar(),b['id']:FakeCalendar()}
    for m in (a,b):svc['store'].save(m['id'],'google',{})
    svc['write'].provider_factory=lambda uid:providers[uid]
    monkeypatch.setenv('CHANDELLE_DEV','1');monkeypatch.setenv('CALENDAR_ALLOW_DEMO_EVENTS','1')
    write=svc['write'];rev=write.status(a,pid)['revision']
    assert write.confirm(a,pid,rev)['approvals']==1
    assert not providers[a['id']].calls
    providers[b['id']].fail=True
    result=write.confirm(b,pid,rev)
    assert result['own_event']['status']=='failed'
    providers[b['id']].fail=False;write.confirm(b,pid,rev);write.confirm(a,pid,rev)
    assert len(providers[a['id']].calls)==1 and len(providers[b['id']].calls)==2
    changed=planning.get(couple['couple_id'],pid);changed['activities'][0]['address']='Autre lieu';planning.save(changed)
    with pytest.raises(ValueError):write.confirm(a,pid,rev)
    new=write.status(a,pid)['revision'];write.confirm(a,pid,new);write.confirm(b,pid,new)
    assert providers[a['id']].calls[-1][0]=='update'
    planning.change(couple['couple_id'],pid,'cancelled');new=write.status(a,pid)['revision']
    write.confirm(a,pid,new);write.confirm(b,pid,new)
    assert providers[a['id']].calls[-1][0]=='delete'

def test_google_freebusy_and_deterministic_crud(monkeypatch):
    provider=GoogleCalendar(None,None,None);fake=MagicMock();monkeypatch.setattr(provider,'service',lambda:fake)
    start=datetime.now(UTC);event=CalendarEvent(title='Sortie',start=start,end=start+timedelta(hours=2),location='',description='')
    fake.freebusy().query().execute.return_value={'calendars':{'primary':{'busy':[{'start':event.start.isoformat(),'end':event.end.isoformat()}]}}}
    assert len(provider.get_busy_slots(event.start,event.end))==1
    assert provider.create_event(event,'stable')==provider.create_event(event,'stable')
    provider.update_event('id',event);provider.delete_event('id')
    assert fake.events().insert.call_args.kwargs['sendUpdates']=='none'
    fake.freebusy().query().execute.return_value={'calendars':{'primary':{'errors':[{'reason':'forbidden'}]}}}
    with pytest.raises(CalendarError):provider.get_busy_slots(event.start,event.end)

def test_outlook_occurrences_pagination_free_and_crud(monkeypatch):
    provider=OutlookCalendar(None,None,None);requests=[];start=datetime.now(UTC);end=start+timedelta(hours=1)
    busy={'start':{'dateTime':start.isoformat(),'timeZone':'UTC'},'end':{'dateTime':end.isoformat(),'timeZone':'UTC'},'showAs':'busy'}
    pages=iter([{'value':[busy,{**busy,'showAs':'free'}],'@odata.nextLink':'https://graph.microsoft.com/v1.0/me/calendarView?$skip=1'}, {'value':[{**busy,'isCancelled':True}]}])
    def request(method,path,**kw):requests.append((method,path,kw));return next(pages) if method=='GET' else {'id':'eid'}
    monkeypatch.setattr(provider,'request',request)
    assert len(provider.get_busy_slots(start,end))==1 and len(requests)==2
    event=CalendarEvent(title='Sortie',start=start,end=end,location='',description='')
    provider.create_event(event,'same');first=requests[-1][2]['json']['transactionId'];provider.create_event(event,'same')
    assert first==requests[-1][2]['json']['transactionId']
    provider.update_event('unsafe/id',event);assert requests[-1][1].endswith('unsafe%2Fid')
    provider.delete_event('eid')

def test_outlook_nextlink_refuses_other_host_before_token():
    with pytest.raises(CalendarError):OutlookCalendar(None,None,None).request('GET','https://evil.example/v1.0/events')

def test_mood_private_old_and_inferred_signals_do_not_become_current(client):
    _,a,_=identities(client);memory=client.app.state.v2['memory'];tracker=MoodTracker(memory.db)
    memory.ingest(a['couple_id'],'PERSON',a['id'],a['id'],'experience','private','Je suis stressé','PRIVATE','manual')
    assert tracker.get_recent_mood(a['id']).confidence==0
    memory.ingest(a['couple_id'],'PERSON',a['id'],a['id'],'experience','old',{'text':'Je suis enthousiaste','signal_at':'2020-01-01T00:00:00+00:00'},'SHARED','inspiration_import')
    assert tracker.get_recent_mood(a['id']).confidence==0
    memory.ingest(a['couple_id'],'PERSON',a['id'],a['id'],'experience','mood',{'text':'Je suis fatigué','signal_at':datetime.now(UTC).isoformat()},'COUPLE_RECOMMENDATION','conversation')
    assert tracker.get_recent_mood(a['id']).mood_label=='fatigué'

def test_opportunity_weights_and_unknown_mood():
    unknown=MoodSignal(user_id='x');good=MoodSignal(user_id='y',mood_label='enthousiaste',confidence=.8)
    tired=MoodSignal(user_id='x',mood_label='fatigué',confidence=.8)
    assert compute_opportunity_score(6,True,good,good)==0
    assert compute_opportunity_score(10,False,good,good)==0
    assert compute_opportunity_score(7,True,unknown,unknown)==.7
    assert compute_opportunity_score(7,True,tired,good)==.55
    assert compute_opportunity_score(7,True,good,good,True)==1

def test_proactive_consents_manual_demo_notifications_dedup_and_ownership(client,monkeypatch):
    couple,a,b=identities(client);setup_slots(client,couple,a,b)
    url='/api/proactive/trigger/'+couple['couple_id']
    assert client.post(url,headers=headers(a),json={'demo':True}).status_code==403
    monkeypatch.setenv('CHANDELLE_DEV','1')
    assert not client.post(url,headers=headers(a),json={'demo':True}).json()['triggered']
    for m in (a,b):assert client.put(PREFIX+'/proactive/settings',headers=headers(m),json={'enabled':True}).status_code==200
    assert not client.post(url,headers=headers(a),json={}).json()['triggered']
    result=client.post(url,headers=headers(a),json={'demo':True})
    assert result.json()['triggered'],result.text
    assert 'mood' not in result.text and 'stress' not in result.text
    result2=client.post(url,headers=headers(a),json={'demo':True}).json();assert not result2['triggered']
    feed=client.get(PREFIX+'/notifications',headers=headers(a)).json()['items'];assert len(feed)==1
    nid=feed[0]['id'];assert client.post(PREFIX+'/notifications/'+nid+'/read',headers=headers(a)).status_code==200
    assert not client.get(PREFIX+'/notifications',headers=headers(b)).json()['items'][0]['read']
    other,x,y=identities(client);assert client.post(PREFIX+'/notifications/'+nid+'/read',headers=headers(x)).status_code==404
    assert client.get(PREFIX+'/notifications',headers=headers(x)).json()['items']==[]
    assert client.get(PREFIX+'/proactive/settings',headers=headers(a)).json()['scheduler']['last_run']
    client.put(PREFIX+'/proactive/settings',headers=headers(a),json={'enabled':False})
    assert client.get(PREFIX+'/notifications',headers=headers(b)).json()['items']==[]

def test_erasure_removes_calendar_and_proactive_consent(client):
    _,a,_=identities(client);store=client.app.state.calendars['store']
    store.save(a['id'],'google',{'refresh_token':'SECRET'})
    client.put(PREFIX+'/proactive/settings',headers=headers(a),json={'enabled':True})
    assert client.delete(PREFIX+'/users/me/data',headers=headers(a)) .status_code==422
    response=client.request('DELETE',PREFIX+'/users/me/data',headers=headers(a),json={'confirmation':'DELETE MY DATA'})
    assert response.status_code==200,response.text
    assert not store.status(a['id'])['connected']
    with store.db.connect() as c:assert not c.execute('SELECT 1 FROM v2_proactive_settings WHERE user_id=?',(a['id'],)).fetchone()

def test_microsoft_oauth_refresh_cache_and_granted_scopes(client,monkeypatch):
    _,a,_=identities(client)
    monkeypatch.setenv('MICROSOFT_CLIENT_ID','test');monkeypatch.setenv('MICROSOFT_CLIENT_SECRET','secret')
    flow={};app=MagicMock()
    def begin(scopes,**kw):
        assert scopes==['Calendars.ReadWrite'];flow.update(kw)
        return {'state':kw['state'],'auth_uri':'https://login.microsoftonline.com/common/oauth2/v2.0/authorize?state='+kw['state'],'code_verifier':'PRIVATE'}
    app.initiate_auth_code_flow.side_effect=begin
    app.acquire_token_by_auth_code_flow.return_value={'access_token':'PRIVATE'}
    monkeypatch.setattr('backend.integrations.calendar.calendar_auth.microsoft_app',lambda cache=None:app)
    r=client.get('/api/calendar/connect/outlook?format=json',headers=headers(a));assert r.status_code==200
    r=client.get('/api/calendar/callback/outlook',params={'state':flow['state'],'code':'code'},follow_redirects=False)
    assert r.headers['location'].endswith('connected')
    svc=client.app.state.calendars;row,data=svc['store'].credentials(a['id']);provider=OutlookCalendar(svc['store'],row,data)
    app.get_accounts.return_value=[{'home_account_id':'test'}]
    app.acquire_token_silent.return_value={'access_token':'REFRESHED'}
    monkeypatch.setattr('backend.integrations.calendar.outlook.microsoft_app',lambda cache=None:app)
    assert provider.token()=='REFRESHED'
    assert app.acquire_token_silent.call_args.args[0]==['Calendars.ReadWrite']
    assert 'REFRESHED' not in client.get(PREFIX+'/calendar/status',headers=headers(a)).text

def test_expired_state_and_cache_require_reconnect_refresh(client,monkeypatch):
    couple,a,b=identities(client);services=client.app.state.calendars;start,end=setup_slots(client,couple,a,b)
    for m in (a,b):services['store'].save(m['id'],'google',{})
    services['read'].provider_factory=lambda _:FakeCalendar()
    assert services['read'].find_common_free_slots(a['id'],b['id'],start,end)
    with services['store'].db.connect() as c:
        c.execute('UPDATE v2_calendar_connections SET synced_at=?',((datetime.now(UTC)-timedelta(minutes=16)).isoformat(),))
    assert not services['read'].cached_common(couple['couple_id'])
    monkeypatch.setenv('GOOGLE_CLIENT_ID','test');monkeypatch.setenv('GOOGLE_CLIENT_SECRET','secret')
    url=services['auth'].begin(a['id'],'google');state=parse_qs(urlsplit(url).query)['state'][0]
    with services['store'].db.connect() as c:c.execute("UPDATE v2_calendar_oauth SET expires_at='2020-01-01T00:00:00+00:00'")
    with pytest.raises(CalendarError):services['auth'].finish('google',{'state':state,'code':'fake'})

def test_cloud_mood_explicit_consent_private_exclusion_and_daily_cap(client,monkeypatch):
    from backend.streams.G_proactive.mood_tracker import MoodAnalysis
    _,a,_=identities(client);db=client.app.state.v2['db'];memory=client.app.state.v2['memory']
    fake=SimpleNamespace(last_mode='openai',_call=MagicMock(return_value=MoodAnalysis(mood_label='positif',confidence=.6)))
    tracker=MoodTracker(db,fake)
    memory.ingest(a['couple_id'],'PERSON',a['id'],a['id'],'experience','cloud',{'text':'La sortie récente m’a fait du bien','signal_at':datetime.now(UTC).isoformat()},'COUPLE_RECOMMENDATION','conversation')
    memory.ingest(a['couple_id'],'PERSON',a['id'],a['id'],'experience','private','PRIVATE-SENTINEL','PRIVATE','conversation')
    monkeypatch.setenv('PROACTIVE_MOOD_OPENAI','1')
    assert tracker.get_recent_mood(a['id']).confidence==0 and fake._call.call_count==0
    client.put(PREFIX+'/proactive/mood-consent',headers=headers(a),json={'enabled':True})
    assert tracker.get_recent_mood(a['id']).confidence==.6
    assert 'PRIVATE-SENTINEL' not in str(fake._call.call_args)
    assert tracker.get_recent_mood(a['id']).confidence==.6 and fake._call.call_count==1
    memory.ingest(a['couple_id'],'PERSON',a['id'],a['id'],'experience','new',{'text':'Une autre expérience','signal_at':datetime.now(UTC).isoformat()},'SHARED','conversation')
    tracker.get_recent_mood(a['id']);assert fake._call.call_count==1
    client.put(PREFIX+'/proactive/mood-consent',headers=headers(a),json={'enabled':False})
    assert tracker.get_recent_mood(a['id']).confidence==0

def test_scheduler_active_state_and_daily_history_use_event_end(client,monkeypatch):
    couple,a,b=identities(client);start,end=setup_slots(client,couple,a,b);scheduler=client.app.state.calendars['scheduler']
    for m in (a,b):client.put(PREFIX+'/proactive/settings',headers=headers(m),json={'enabled':True})
    with scheduler.db.connect() as c:c.execute('UPDATE v2_couples SET created_at=? WHERE id=?',((datetime.now(UTC)-timedelta(days=30)).isoformat(),couple['couple_id']))
    p=query(client,a,time_window={'start':start.isoformat(),'end':end.isoformat()})['plans'][0]
    plan=client.app.state.v2['planning'];plan.change(couple['couple_id'],p['id'],'accepted')
    assert 'déjà prévue' in scheduler.run(couple['couple_id'])['reason']
    p=plan.get(couple['couple_id'],p['id']);p['start']=(datetime.now(UTC)-timedelta(days=2,hours=2)).isoformat();p['end']=(datetime.now(UTC)-timedelta(days=2)).isoformat();plan.save(p)
    assert 'moins de sept' in scheduler.run(couple['couple_id'])['reason']
    p['start']=(datetime.now(UTC)-timedelta(days=8,hours=2)).isoformat();p['end']=(datetime.now(UTC)-timedelta(days=8)).isoformat();plan.save(p)
    assert scheduler.run(couple['couple_id'])['triggered']
    monkeypatch.setenv('PROACTIVE_SCHEDULER_ENABLED','1')
    try:
        scheduler.start();assert scheduler.status(couple['couple_id'])['running']
        assert scheduler.status(couple['couple_id'])['next_run']
        assert scheduler.run(couple['couple_id'],scheduled=True)['reason']=='Déjà vérifié.'
    finally:scheduler.stop()

def test_conversation_mood_uses_original_visibility(client):
    from backend.streams.H_conversation.service import Conversation, ConversationService
    from backend.integrations.openai import OpenAIAdapter
    _,a,_=identities(client);db=client.app.state.v2['db'];memory=client.app.state.v2['memory']
    convo=ConversationService(db,memory)
    convo.ingest(a,Conversation(text='Je suis fatigué.',privacy_scope='PRIVATE'),OpenAIAdapter(enabled=False,db=db))
    assert MoodTracker(db).get_recent_mood(a['id']).confidence==0
    convo.ingest(a,Conversation(text='Je suis enthousiaste.',privacy_scope='COUPLE_RECOMMENDATION'),OpenAIAdapter(enabled=False,db=db))
    assert MoodTracker(db).get_recent_mood(a['id']).mood_label=='enthousiaste'
