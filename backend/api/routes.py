"""Authenticated local V2 API. Capability identity is for local demonstration."""
from pathlib import Path
from typing import Literal
import json
import os
from uuid import uuid4
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from backend.api.reels import install_reel_routes
from backend.integrations.calendar.store import calendar_locked
from backend.db import Database
from backend.streams.B_memory.onboarding import OnboardingService, CoupleCreate, Answer
from backend.streams.B_memory.service import Privacy
from backend.db import now, encoded
from backend.streams.E_orchestrator.service import PlanningService, Query, Review
from backend.streams.A_calendar.service import AvailabilityService, AvailabilityInput, GoogleCalendarInput
from backend.streams.F_booking.service import prepare, calendar
from backend.streams.D_connectors.service import InspirationService, SignalImport, SignalConfirm
from backend.integrations.openai import OpenAIAdapter
from backend.integrations.dialogue import DialogueUnavailable
from backend.integrations.gradium import GradiumAdapter, SpeechUnavailable
from backend.integrations.google_calendar import download_calendar, CalendarUnavailable
from starlette.concurrency import run_in_threadpool
from backend.streams.H_conversation.voice import DiscoveryTurn, SpeechText, discovery_turn
from backend.integrations.ai_budget import AIBudget
from backend.streams.H_conversation.dialogue import DiscoveryDialogue, ChatTurn, DialogueConflict
from backend.streams.C_discovery.recommendations import RealRecommendations
from backend.streams.C_discovery.web import WebDiscovery, WebQuery
from backend.streams.B_memory.service import MemoryServiceV2
from backend.streams.C_discovery.service import CatalogService
from backend.streams.G_proactive.service import SuggestionService
from backend.streams.H_conversation.service import Conversation, ConversationService

class MemoryCreate(BaseModel):
    scope: Literal['PERSON','COUPLE','SESSION','DATE']='PERSON'
    entity_id: str
    category: str = Field(min_length=1,max_length=100)
    key: str = Field(min_length=1,max_length=200)
    value: str | dict | list | float | int
    privacy_scope: Privacy='PRIVATE'

class MemoryPatch(BaseModel):
    value: str | dict | list | float | int | None = None
    category: str | None = Field(default=None,min_length=1,max_length=100)
    tags: list[str] | None = None
    privacy_scope: Privacy | None = None
    salience: float | None = Field(default=None,ge=0,le=1)
    confidence: float | None = Field(default=None,ge=0,le=1)
    model_config = {'extra':'forbid'}

class Share(BaseModel):privacy_scope: Privacy
class State(BaseModel):state: Literal['saved','liked','disliked','rejected','neutral']
class PlanChange(BaseModel):
    status: Literal['draft','proposed','accepted','completed','cancelled'] | None=None
    kept_ids: list[str] | None=None
class Comparison(BaseModel):
    activity_ids: list[str] = Field(min_length=1,max_length=5)

class Replacement(BaseModel):activity_id: str
class Action(BaseModel):action: Literal['viewed','accepted','dismissed','snoozed','regenerate']
class Reset(BaseModel):confirmation: str
def install_routes(app,db_path):
    db=Database(db_path)
    memory=MemoryServiceV2(db)
    onboarding=OnboardingService(db,memory)
    catalog=CatalogService(db,memory);catalog.remove_synthetic()
    availability=AvailabilityService(db)
    inspirations=InspirationService(memory)
    planning=PlanningService(db,memory,catalog)
    suggestions=SuggestionService(db,planning)
    conversations=ConversationService(db,memory)
    web_discovery=WebDiscovery(db,memory)
    real_recommendations=RealRecommendations(db,memory)
    dialogue=DiscoveryDialogue(db,planning,real_recommendations,web_discovery)
    app.state.v2={'db':db,'memory':memory,'onboarding':onboarding,'catalog':catalog,'planning':planning,'suggestions':suggestions,'availability':availability,'inspirations':inspirations,'dialogue':dialogue,'real_recommendations':real_recommendations}
    planning.web=web_discovery
    router=APIRouter(prefix='/api/v2')

    def auth(x_member_token: str | None=Header(default=None)):
        return onboarding.authenticate(x_member_token)

    def ready(member=Depends(auth)):
        if not onboarding.status(member['couple_id'])['completed']:raise HTTPException(409,'Complete both interviews first')
        return member

    reels=install_reel_routes(app,db,memory,ready)
    from backend.api.calendar import install_calendar_routes
    calendars=install_calendar_routes(app,db,planning,suggestions,ready)
    from backend.api.dates import install_date_routes
    install_date_routes(app,planning,ready)

    def own_couple(cid,member):
        if cid!=member['couple_id']:raise PermissionError('Different couple')

    def entity(scope,eid,member):
        if scope=='PERSON' and eid!=member['id']:raise PermissionError('Personal memories belong to their owner')
        if scope=='COUPLE' and eid!=member['couple_id']:raise PermissionError('Different couple')
        if scope=='DATE':planning.get(member['couple_id'],eid)
        if scope=='SESSION':
            with db.connect() as c:r=c.execute('SELECT id FROM v2_conversations WHERE id=? AND user_id=?',(eid,member['id'])).fetchone()
            if not r:raise PermissionError('Unknown personal session')

    @router.get('/health')
    def health():return {'status':'ok','version':'2.0','schema_version':1,'extensions':{'peer_merge':1,'google_ical':1},'offline':True}

    @router.get('/integrations')
    def integrations():
        from backend.integrations.dialogue import DialogueAdapter
        from backend.streams.C_discovery.local_catalog import ImportedCatalog
        return {'gradium':GradiumAdapter().status(),
                'openai':{**OpenAIAdapter().status(),'web_enabled':os.getenv('OPENAI_WEB_ENABLED')=='1'},
                'dialogue':{**DialogueAdapter().status(),'requires_consent':True,'activation':'ask_submit','session_hours':2},
                'calendar':{'mode':'manual_or_connected','timezone':'Europe/Paris','ics_export':True,
                    'google_ical_import':True,'automatic_sync':False,
                    'providers':{p:calendars['auth'].configured(p) for p in ('google','outlook')},
                    'apple_caldav':False,'scheduler_running':bool(calendars['scheduler'].scheduler and calendars['scheduler'].scheduler.running)},
                'catalog':{'mode':'imported_and_web',**ImportedCatalog(db).status()},
                'schema_version':1,'extensions':{'peer_merge':1,'calendar_proactive':1,'google_ical':1,'voice':1,'discovery_dialogue':1},
                'developer_mode':os.getenv('CHANDELLE_DEV')=='1'}

    @router.post('/onboarding/couples')
    def create(body:CoupleCreate):return onboarding.create(body)

    @router.get('/onboarding/status')
    def status(couple_id:str|None=None):
        if not couple_id:return {'status':'not_started','completed':False,'members':[]}
        return onboarding.status(couple_id)

    @router.get('/onboarding/couples/{cid}/members/{uid}')
    def interview(cid:str,uid:str,member=Depends(auth)):return onboarding.member(cid,uid,member)

    @router.put('/onboarding/couples/{cid}/members/{uid}/answers')
    def answer(cid:str,uid:str,body:Answer,member=Depends(auth)):return onboarding.answer(cid,uid,member,body)

    @router.post('/onboarding/couples/{cid}/members/{uid}/complete')
    def complete(cid:str,uid:str,member=Depends(auth)):return onboarding.complete(cid,uid,member)

    @router.get('/users')
    def users(member=Depends(auth)):return {'items':onboarding.status(member['couple_id'])['members']}

    @router.get('/couples')
    def couples(member=Depends(auth)):return {'items':[onboarding.status(member['couple_id'])]}

    @router.get('/couples/{cid}/profile')
    def couple_profile(cid:str,member=Depends(ready)):
        own_couple(cid,member)
        return memory.derive_couple(cid)

    @router.get('/profiles/{scope}/{eid}')
    def profile(scope:str,eid:str,member=Depends(ready)):
        entity(scope,eid,member)
        return memory.profile(member['couple_id'],scope,eid,member['id'])

    @router.get('/memories/search')
    def search(scope:str,entity_id:str,query:str='',limit:int=20,member=Depends(ready)):
        entity(scope,entity_id,member)
        return {'items':memory.search(member['couple_id'],scope,entity_id,member['id'],query,limit)}

    @router.get('/memories')
    def memories(scope:str='PERSON',entity_id:str|None=None,member=Depends(ready)):
        eid=entity_id or member['id'];entity(scope,eid,member)
        items=memory.list_facts(member['couple_id'],scope,eid,member['id'])
        return {'items':items,'total':len(items)}

    @router.post('/memories')
    def add_memory(body:MemoryCreate,member=Depends(ready)):
        entity(body.scope,body.entity_id,member)
        if len(encoded(body.value))>8000:raise ValueError('Memory too large')
        return memory.ingest(member['couple_id'],body.scope,body.entity_id,member['id'],body.category,body.key,body.value,body.privacy_scope,'manual')

    @router.patch('/memories/{mid}')
    def edit_memory(mid:str,body:MemoryPatch,member=Depends(ready)):
        changes=body.model_dump(exclude_unset=True)
        if any(value is None for value in changes.values()):raise ValueError('Memory fields cannot be null')
        return memory.update(mid,member['id'],**changes)

    @router.delete('/memories/{mid}')
    def delete_memory(mid:str,member=Depends(ready)):
        memory.delete(mid,member['id']);return {'deleted':True}

    @router.post('/memories/{mid}/share')
    def share_memory(mid:str,body:Share,member=Depends(ready)):return memory.share(mid,member['id'],body.privacy_scope)

    @router.get('/memories/export/{scope}/{eid}')
    def export(scope:str,eid:str,member=Depends(ready)):
        entity(scope,eid,member)
        return memory.export_entity(member['couple_id'],scope,eid,member['id'])

    @router.get('/memories/{mid}/provenance')
    def provenance(mid:str,member=Depends(ready)):
        return {'items':memory.provenance(mid,member['id'])}

    @router.delete('/memories/entity/{scope}/{eid}')
    def erase_entity(scope:str,eid:str,member=Depends(ready)):
        entity(scope,eid,member)
        if scope=='PERSON' and eid==member['id']:
            reels.cancel(member)
            with db.connect() as c:c.execute('DELETE FROM v2_web_cache WHERE owner_id=?',(member['id'],))
        return memory.delete_entity(member['couple_id'],scope,eid,member['id'])

    @router.get('/ai/budget')
    def ai_budget(member=Depends(ready)):return AIBudget(db).status()

    @router.post('/discovery/web')
    def web_search(body:WebQuery,member=Depends(ready)):
        # Compatibility alias into the SAME search orchestrator used by Ask and Discover.
        values={'text':body.text,'mode':'auto','use_shared_interests':body.use_shared_interests}
        if body.plan:
            values.update({k:v for k,v in body.plan.model_dump().items() if k in ('budget','categories','activity_count','radius_km') and v is not None})
            if body.plan.date:
                from datetime import datetime,timedelta
                start=datetime.combine(body.plan.date,body.plan.time or datetime.min.time().replace(hour=18))
                values['time_window']={'start':start,'end':start+timedelta(hours=6)}
        result=planning.query(member['couple_id'],Query.model_validate(values),deck_options={'owner_id':member['id'],'duration':360,'travel':30})
        return {**result,'search_id':result['run_id'],'proposals':result['plans'],'answer':result['message'],'segments':[]}

    @router.get('/activities/real')
    def real_activities(query:str='',category:str='',member=Depends(ready)):
        from backend.integrations.dialogue import SearchIntent
        intent=SearchIntent(summary=query,categories=[category] if category else [])
        found=real_recommendations.search(member['couple_id'],intent,limit=100)
        return {'items':found['items'],'total':found['total']}

    @router.get('/activities')
    def activities(query:str='',category:str|None=None,limit:int=30,offset:int=0,member=Depends(ready)):
        # These former catalogue routes expose no alternate source. Explicit search is required.
        return catalog.browse(query,category,limit,offset)

    @router.get('/activities/{aid}')
    def activity(aid:str,member=Depends(ready)):return catalog.get(aid)

    @router.post('/activities/{aid}/state')
    def activity_state(aid:str,body:State,member=Depends(ready)):
        return catalog.record_state(member['couple_id'],member['id'],aid,body.state)

    @router.post('/recommendations/query')
    def recommend(body:Query,member=Depends(ready)):
        # Recommendation text belongs to its author, regardless of plan visibility.
        interaction=conversations.ingest(member,Conversation(text=body.text),OpenAIAdapter(enabled=False))
        result=planning.query(member['couple_id'],body,deck_options={'owner_id':member['id'],'duration':360,'travel':30})
        return {**result,'conversation_id':interaction['conversation_id']}


    @router.post('/ask/chat')
    @router.post('/discover/chat', include_in_schema=False)
    def ask_chat(body: ChatTurn | DiscoveryTurn, member=Depends(ready)):
        if isinstance(body,ChatTurn):
            try:
                return dialogue.turn(member,body)
            except DialogueConflict as exc:
                raise HTTPException(409,str(exc)) from None
            except DialogueUnavailable as exc:
                return JSONResponse(status_code=503,content={'error':{'code':exc.code,'message':str(exc)}})
        return discovery_turn(body, lambda text, budget: planning.query(member['couple_id'],
            Query(text=text, budget=budget, activity_count=2, max_plans=3, mode='auto'),
            deck_options={'owner_id':member['id'],'duration':360,'travel':30}))

    @router.delete('/ask/chat/{session_id}')
    @router.delete('/discover/chat/{session_id}', include_in_schema=False)
    def close_ask_chat(session_id:str,member=Depends(auth)):
        return dialogue.close(member,session_id)

    @router.post('/voice/transcribe')
    async def transcribe(request: Request, member=Depends(ready)):
        if request.headers.get('content-type', '').split(';')[0] != 'audio/wav':
            raise HTTPException(415, 'Audio WAV requis')
        audio = bytearray()
        async for chunk in request.stream():
            audio.extend(chunk)
            if len(audio) > 4_500_000:
                raise HTTPException(413, 'Prise de parole trop longue')
        try:
            return {'text': await GradiumAdapter().transcribe(bytes(audio))}
        except SpeechUnavailable as exc:
            raise HTTPException(503, str(exc)) from None

    @router.post('/voice/speak')
    async def speak(body: SpeechText, member=Depends(ready)):
        try:
            audio = await GradiumAdapter().speak(body.text)
        except SpeechUnavailable as exc:
            raise HTTPException(503, str(exc)) from None
        return Response(audio, media_type='audio/wav', headers={'Cache-Control': 'private, no-store'})

    @router.get('/availability')
    def availability_state(member=Depends(ready)):
        return availability.state(member['couple_id'],member['id'])

    @router.put('/availability')
    def availability_save(body:AvailabilityInput,member=Depends(ready)):
        return availability.save(member['couple_id'],member['id'],body)

    @router.post('/availability/google-calendar')
    async def import_google_calendar(body: GoogleCalendarInput, member=Depends(ready)):
        try:
            data = await download_calendar(body.url.get_secret_value())
        except CalendarUnavailable as exc:
            raise HTTPException(502, str(exc)) from None
        return await run_in_threadpool(availability.import_calendar, member['couple_id'], member['id'], body, data)

    @router.get('/inspirations')
    def inspiration_list(member=Depends(ready)):
        return inspirations.list(member['couple_id'],member['id'])

    @router.post('/inspirations/import')
    def inspiration_import(body:SignalImport,member=Depends(ready)):
        return inspirations.ingest(member['couple_id'],member['id'],body)

    @router.post('/inspirations/{mid}/confirm')
    def inspiration_confirm(mid:str,body:SignalConfirm,member=Depends(ready)):
        return inspirations.confirm(mid,member['id'],body)

    @router.post('/activities/compare')
    def compare(body:Comparison,member=Depends(ready)):
        selected=[catalog.get(aid) for aid in dict.fromkeys(body.activity_ids)]
        known=sum(a['price_per_person']*2 for a in selected if a['price_per_person'] is not None)
        complete=all(a['price_per_person'] is not None for a in selected)
        return {'items':selected,'known_total_eur':known,'budget_complete':complete,
                'total_couple_cost':known if complete else None,'composition_limit':3,
                'message':'Comparaison indicative ; la composition vérifie horaires, budget et préférences.'}

    @router.post('/date-plans/{pid}/booking')
    def prepare_booking(pid:str,member=Depends(ready)):
        return prepare(planning.get(member['couple_id'],pid))

    @router.get('/date-plans/{pid}/calendar')
    def export_calendar(pid:str,member=Depends(ready)):
        return Response(calendar(planning.get(member['couple_id'],pid)),media_type='text/calendar; charset=utf-8',
                        headers={'Content-Disposition':f'attachment; filename="chandelle-{pid}.ics"','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

    @router.get('/date-plans')
    def plans(member=Depends(ready)):return planning.list(member['couple_id'])

    @router.get('/date-plans/{pid}')
    def plan(pid:str,member=Depends(ready)):return planning.public(planning.get(member['couple_id'],pid,member['id']))

    @router.patch('/date-plans/{pid}')
    @calendar_locked
    def change_plan(pid:str,body:PlanChange,member=Depends(ready)):return planning.change(member['couple_id'],pid,body.status,body.kept_ids)

    @router.post('/date-plans/{pid}/replace')
    @calendar_locked
    def replace_plan(pid:str,body:Replacement,member=Depends(ready)):return planning.replace(member['couple_id'],pid,body.activity_id)

    @router.post('/date-plans/{pid}/feedback')
    def feedback(pid:str,body:Review,member=Depends(ready)):return planning.review(member['couple_id'],pid,member['id'],body)

    @router.get('/history')
    def history(member=Depends(ready)):return planning.list(member['couple_id'],True)

    @router.get('/history/{pid}')
    def history_detail(pid:str,member=Depends(ready)):return plan(pid,member)

    @router.get('/suggestions')
    def feed(member=Depends(ready)):return suggestions.list(member['couple_id'])

    @router.post('/suggestions/check')
    @calendar_locked
    def check(member=Depends(ready)):return suggestions.check(member['couple_id'])

    @router.post('/suggestions/{sid}/action')
    @calendar_locked
    def suggestion_action(sid:str,body:Action,member=Depends(ready)):return suggestions.action(member['couple_id'],sid,body.action,member['id'])

    @router.get('/runs/{rid}')
    def run(rid:str,member=Depends(ready)):
        with db.connect() as c:r=c.execute('SELECT payload FROM v2_runs WHERE id=? AND couple_id=?',(rid,member['couple_id'])).fetchone()
        if not r:raise KeyError('Unknown run')
        payload=json.loads(r[0])
        owner=payload.get('_owner_id') or payload.get('_activity_search',{}).get('_deck',{}).get('owner_id')
        if owner and owner!=member['id']:raise PermissionError('Recherche personnelle inaccessible.')
        return planning.public(payload)

    upload_dir=Path(db_path).parent/'uploads'

    @router.post('/uploads')
    async def upload(request:Request,plan_id:str,member=Depends(ready),x_filename:str=Header(default='photo.png')):
        planning.get(member['couple_id'],plan_id)
        mime=request.headers.get('content-type','').split(';')[0]
        extension=Path(x_filename).suffix.lower()
        if mime not in ('image/png','image/jpeg') or extension not in ({'.png'} if mime=='image/png' else {'.jpg','.jpeg'}):raise ValueError('Only PNG and JPEG photos are accepted')
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>5*1024*1024:raise HTTPException(413,'Photo limit is 5 MB')
        if not data or (mime=='image/png' and (not data.startswith(b'\x89PNG\r\n\x1a\n') or b'IEND' not in data[-16:])) or (mime=='image/jpeg' and (not data.startswith(b'\xff\xd8\xff') or not data.endswith(b'\xff\xd9'))):raise ValueError('Photo content does not match MIME type')
        uid=uuid4().hex;filename=uid+('.png' if mime=='image/png' else '.jpg')
        upload_dir.mkdir(parents=True,exist_ok=True)
        (upload_dir/filename).write_bytes(data)
        with db.connect() as c:c.execute('INSERT INTO v2_uploads VALUES(?,?,?,?,?,?,?)',(uid,plan_id,member['id'],filename,mime,len(data),now()))
        return {'id':uid,'plan_id':plan_id,'mime':mime,'size':len(data)}

    def photo(uid,member):
        with db.connect() as c:r=c.execute('SELECT * FROM v2_uploads WHERE id=? AND user_id=?',(uid,member['id'])).fetchone()
        if not r:raise KeyError('Unknown photo')
        return dict(r)

    @router.get('/uploads/{uid}')
    def get_photo(uid:str,member=Depends(ready)):
        item=photo(uid,member)
        return FileResponse(upload_dir/item['filename'],media_type=item['mime'],headers={'X-Content-Type-Options':'nosniff','Cache-Control':'private, no-store'})

    @router.delete('/uploads/{uid}')
    def delete_photo(uid:str,member=Depends(ready)):
        item=photo(uid,member)
        (upload_dir/item['filename']).unlink(missing_ok=True)
        with db.connect() as c:c.execute('DELETE FROM v2_uploads WHERE id=?',(uid,))
        return {'deleted':True}

    @router.get('/conversations')
    def conversation_list(limit:int=100,offset:int=0,member=Depends(ready)):
        return conversations.list(member,limit,offset)

    @router.get('/conversations/{sid}')
    def conversation_history(sid:str,member=Depends(ready)):
        return conversations.history(member,sid)

    @router.post('/conversations')
    def conversation(body:Conversation,member=Depends(ready)):
        adapter=OpenAIAdapter(enabled=body.mode in {'openai','auto'} and OpenAIAdapter().enabled,db=db)
        return conversations.ingest(member,body,adapter)

    def dev():
        if os.getenv('CHANDELLE_DEV')!='1':raise HTTPException(403,'Developer mode is disabled')

    @router.delete('/users/me/data')
    @calendar_locked
    def erase_person(body:Reset,member=Depends(auth)):
        if body.confirmation!='DELETE MY DATA':raise ValueError('Explicit personal erasure confirmation required')
        reels.cancel(member)
        calendars['store'].disconnect(member['id'])
        uid,cid=member['id'],member['couple_id']
        with db.connect() as c:
            scopes=[tuple(r) for r in c.execute('SELECT DISTINCT scope,entity_id FROM v2_facts WHERE couple_id=? AND owner_id=?',(cid,uid))]
            photos=[r[0] for r in c.execute('SELECT filename FROM v2_uploads WHERE user_id=?',(uid,))]
        for scope,eid in scopes:memory.delete_entity(cid,scope,eid,uid)
        with db.connect() as c:
            c.execute('DELETE FROM v2_proactive_settings WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_mood_cloud WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_mood_cache WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_notification_reads WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_web_cache WHERE owner_id=?',(uid,))
            c.execute('DELETE FROM v2_discovery_sessions WHERE owner_id=?',(uid,))
            c.execute('DELETE FROM v2_messages WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_conversations WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_answers WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_reviews WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_uploads WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_activity_states WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_availability WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_calendar_imports WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_snapshots WHERE entity_id IN (?,?)',(uid,cid))
            c.execute("UPDATE v2_memberships SET status='not_started',current_step=1,completed_at=NULL WHERE user_id=?",(uid,))
            c.execute("UPDATE v2_couples SET onboarding_status='in_progress',profile_version=0 WHERE id=?",(cid,))
            c.execute('UPDATE v2_users SET name=? WHERE id=?',('Person '+member['role'],uid))
            c.execute("UPDATE v2_suggestions SET state='expired' WHERE couple_id=? AND state IN ('new','viewed','snoozed')",(cid,))
        for filename in photos:(upload_dir/filename).unlink(missing_ok=True)
        memory.derive_couple(cid)
        return {'erased':True,'status':onboarding.status(cid),'retained':'Local capability and membership for resume; shared date plans remain couple records'}

    @router.post('/dev/reset')
    @calendar_locked
    def reset(body:Reset):
        dev()
        if body.confirmation!='RESET LOCAL V2':raise ValueError('Explicit reset confirmation required')
        with db.connect() as c:
            tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v2_%'") if r[0] not in ('v2_schema','v2_extensions','v2_ai_calls')]
            c.execute('PRAGMA foreign_keys=OFF')
            for table in tables:
                # FTS5 owns its shadow tables; deleting those directly corrupts the index.
                if table.replace('_','').isalnum() and not table.startswith('v2_activity_search_'):c.execute('DELETE FROM "'+table+'"')
        if upload_dir.exists():
            for file in upload_dir.iterdir():
                if file.is_file() and len(file.stem)==32 and all(x in '0123456789abcdef' for x in file.stem):file.unlink()
        return {'reset':True}

    app.include_router(router)
