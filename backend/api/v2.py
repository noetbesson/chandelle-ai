"""Authenticated local V2 API. Capability identity is for local demonstration."""
from pathlib import Path
from typing import Literal
import json
import os
from uuid import uuid4
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from backend.db import Database
from backend.domain.onboarding import OnboardingService, CoupleCreate, Answer, Privacy, now, encoded
from backend.domain.planning import PlanningService, Query, Review
from backend.integrations.openai import OpenAIAdapter
from backend.streams.B_memory.v2 import MemoryServiceV2
from backend.streams.C_discovery.v2 import CatalogService
from backend.streams.G_proactive.v2 import SuggestionService

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
class Replacement(BaseModel):activity_id: str
class Action(BaseModel):action: Literal['viewed','accepted','dismissed','snoozed','regenerate']
class Reset(BaseModel):confirmation: str
class Conversation(BaseModel):
    text: str=Field(min_length=1,max_length=4000)
    privacy_scope: Privacy='PRIVATE'
    mode: Literal['offline','openai']='offline'


def install_v2(app,db_path):
    db=Database(db_path)
    memory=MemoryServiceV2(db)
    onboarding=OnboardingService(db,memory)
    catalog=CatalogService(db,memory);catalog.seed()
    planning=PlanningService(db,memory,catalog)
    suggestions=SuggestionService(db,planning)
    app.state.v2={'db':db,'memory':memory,'onboarding':onboarding,'catalog':catalog,'planning':planning,'suggestions':suggestions}
    router=APIRouter(prefix='/api/v2')

    def auth(x_member_token: str | None=Header(default=None)):
        return onboarding.authenticate(x_member_token)

    def ready(member=Depends(auth)):
        if not onboarding.status(member['couple_id'])['completed']:raise HTTPException(409,'Complete both interviews first')
        return member

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
    def health():return {'status':'ok','version':'2.0','schema_version':1,'offline':True}

    @router.get('/integrations')
    def integrations():return {'openai':OpenAIAdapter().status(),'calendar':{'mode':'mock'},'catalog':{'mode':'internal_demo'},'schema_version':1,'developer_mode':os.getenv('CHANDELLE_DEV')=='1'}

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
        return memory.delete_entity(member['couple_id'],scope,eid,member['id'])

    @router.get('/activities')
    def activities(query:str='',category:str|None=None,limit:int=30,offset:int=0,member=Depends(ready)):
        result=catalog.browse(query,category,limit,offset)
        scores={x['activity']['id']:x for x in catalog.discover(member['couple_id'],__import__('backend.streams.H_conversation.service',fromlist=['default_availability']).default_availability(),limit=100)}
        with db.connect() as c:states={r['activity_id']:r['state'] for r in c.execute('SELECT * FROM v2_activity_states WHERE user_id=?',(member['id'],))}
        for item in result['items']:
            score=scores.get(item['id'])
            if score:item.update({k:score[k] for k in ('person_a_score','person_b_score','couple_score','evidence','components')})
            item['state']=states.get(item['id'],'neutral');item['eligible']=score is not None
        return result

    @router.get('/activities/{aid}')
    def activity(aid:str,member=Depends(ready)):return catalog.get(aid)

    @router.post('/activities/{aid}/state')
    def activity_state(aid:str,body:State,member=Depends(ready)):
        result=catalog.set_state(member['id'],aid,body.state)
        activity=catalog.get(aid)
        previous=[f for f in memory.list_facts(member['couple_id'],'PERSON',member['id'],member['id']) if f['key']=='activity:'+aid]
        if body.state in ('liked','saved','disliked','rejected'):
            memory.ingest(member['couple_id'],'PERSON',member['id'],member['id'],'dislikes' if body.state in ('disliked','rejected') else 'interests','activity:'+aid,{'values':[activity['category']]},'COUPLE_RECOMMENDATION','activity_feedback',supersedes=previous[0]['id'] if previous else None)
            for old in previous[1:]:memory.delete(old['id'],member['id'])
        else:
            for old in previous:memory.delete(old['id'],member['id'])
        return result

    @router.post('/recommendations/query')
    def recommend(body:Query,member=Depends(ready)):return planning.query(member['couple_id'],body)

    @router.get('/date-plans')
    def plans(member=Depends(ready)):return planning.list(member['couple_id'])

    @router.get('/date-plans/{pid}')
    def plan(pid:str,member=Depends(ready)):return planning.public(planning.get(member['couple_id'],pid,member['id']))

    @router.patch('/date-plans/{pid}')
    def change_plan(pid:str,body:PlanChange,member=Depends(ready)):return planning.change(member['couple_id'],pid,body.status,body.kept_ids)

    @router.post('/date-plans/{pid}/replace')
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
    def check(member=Depends(ready)):return suggestions.check(member['couple_id'])

    @router.post('/suggestions/{sid}/action')
    def suggestion_action(sid:str,body:Action,member=Depends(ready)):return suggestions.action(member['couple_id'],sid,body.action,member['id'])

    @router.get('/runs/{rid}')
    def run(rid:str,member=Depends(ready)):
        with db.connect() as c:r=c.execute('SELECT payload FROM v2_runs WHERE id=? AND couple_id=?',(rid,member['couple_id'])).fetchone()
        if not r:raise KeyError('Unknown run')
        return json.loads(r[0])

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

    @router.post('/conversations')
    def conversation(body:Conversation,member=Depends(ready)):
        adapter=OpenAIAdapter(enabled=body.mode=='openai' and OpenAIAdapter().enabled)
        extraction=adapter.extract(body.text,member['id'])
        sid=uuid4().hex
        with db.connect() as c:
            c.execute('INSERT INTO v2_conversations VALUES(?,?,?,?)',(sid,member['couple_id'],member['id'],now()))
            c.execute('INSERT INTO v2_messages VALUES(?,?,?,?,?)',(uuid4().hex,sid,member['id'],body.text,now()))
        facts=[memory.ingest(member['couple_id'],'PERSON',member['id'],member['id'],f.category,'conversation:'+sid+':'+str(i),{'values':[f.value]},body.privacy_scope,'conversation') for i,f in enumerate(extraction.facts)]
        return {'conversation_id':sid,'facts':facts,'mode':adapter.last_mode}

    def dev():
        if os.getenv('CHANDELLE_DEV')!='1':raise HTTPException(403,'Developer mode is disabled')

    @router.delete('/users/me/data')
    def erase_person(body:Reset,member=Depends(auth)):
        if body.confirmation!='DELETE MY DATA':raise ValueError('Explicit personal erasure confirmation required')
        uid,cid=member['id'],member['couple_id']
        with db.connect() as c:
            scopes=[tuple(r) for r in c.execute('SELECT DISTINCT scope,entity_id FROM v2_facts WHERE couple_id=? AND owner_id=?',(cid,uid))]
            photos=[r[0] for r in c.execute('SELECT filename FROM v2_uploads WHERE user_id=?',(uid,))]
        for scope,eid in scopes:memory.delete_entity(cid,scope,eid,uid)
        with db.connect() as c:
            c.execute('DELETE FROM v2_messages WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_conversations WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_answers WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_reviews WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_uploads WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_activity_states WHERE user_id=?',(uid,))
            c.execute('DELETE FROM v2_snapshots WHERE entity_id IN (?,?)',(uid,cid))
            c.execute("UPDATE v2_memberships SET status='not_started',current_step=1,completed_at=NULL WHERE user_id=?",(uid,))
            c.execute("UPDATE v2_couples SET onboarding_status='in_progress',profile_version=0 WHERE id=?",(cid,))
            c.execute('UPDATE v2_users SET name=? WHERE id=?',('Person '+member['role'],uid))
            c.execute("UPDATE v2_suggestions SET state='expired' WHERE couple_id=? AND state IN ('new','viewed','snoozed')",(cid,))
        for filename in photos:(upload_dir/filename).unlink(missing_ok=True)
        memory.derive_couple(cid)
        return {'erased':True,'status':onboarding.status(cid),'retained':'Local capability and membership for resume; shared date plans remain couple records'}

    @router.post('/dev/seed')
    def seed():
        dev();result=onboarding.create(CoupleCreate(person_a='Alex',person_b='Sam'))
        for person in result['members']:
            member=onboarding.authenticate(person['token'])
            values=[{'name':person['name']},{'values':['culture','food','outdoors']},{'values':[]},{'min':20,'max':120,'unit':'couple','flexible':False},{'novelty':.7},{'days':[],'travel_minutes':60,'dietary':[],'accessibility':[]},{'skip':True}]
            for step,value in enumerate(values,1):onboarding.answer(result['couple_id'],person['id'],member,Answer(step=step,value=value,privacy_scope='SHARED' if step==2 else 'COUPLE_RECOMMENDATION'))
            onboarding.complete(result['couple_id'],person['id'],member)
        result['status']=onboarding.status(result['couple_id'])
        return result

    @router.post('/dev/reset')
    def reset(body:Reset):
        dev()
        if body.confirmation!='RESET LOCAL V2':raise ValueError('Explicit reset confirmation required')
        with db.connect() as c:
            tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v2_%'") if r[0]!='v2_schema']
            c.execute('PRAGMA foreign_keys=OFF')
            for table in tables:
                if table.replace('_','').isalnum():c.execute('DELETE FROM "'+table+'"')
        if upload_dir.exists():
            for file in upload_dir.iterdir():
                if file.is_file() and len(file.stem)==32 and all(x in '0123456789abcdef' for x in file.stem):file.unlink()
        catalog.seed();return {'reset':True}

    app.include_router(router)
