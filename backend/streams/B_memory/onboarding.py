"""Durable, separately scoped interviews for a shared local device."""
from hashlib import sha256
import json
import secrets
from threading import RLock
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict, model_validator

from backend.db import now, encoded
from .service import Privacy

class CoupleCreate(BaseModel):
    person_a: str = Field(min_length=1, max_length=60)
    person_b: str = Field(min_length=1, max_length=60)

class Answer(BaseModel):
    model_config = ConfigDict(extra='forbid')
    step: int = Field(ge=1, le=7)
    value: dict
    privacy_scope: Privacy = 'COUPLE_RECOMMENDATION'

    @model_validator(mode='after')
    def validate_answer(self):
        if len(encoded(self.value)) > 4000:
            raise ValueError('Answer too long')
        if self.value.get('skip'):
            if self.step == 1:
                raise ValueError('Identity is required')
            self.value = {'skip': True}
            return self
        allowed = {1:{'name','pronouns'},2:{'values'},3:{'values'},4:{'min','max','flexible','unit'},5:{'energy','social','novelty','outdoor','duration'},6:{'days','travel_minutes','dietary','accessibility'},7:{'text'}}[self.step]
        if set(self.value) - allowed:
            raise ValueError('Unexpected answer field')
        if self.step == 1 and (not isinstance(self.value.get('name'),str) or not 1 <= len(self.value['name'].strip()) <= 60):
            raise ValueError('Name is required')
        if self.step in (2,3):
            if not isinstance(self.value.get('values',[]),list) or any(not isinstance(x,str) or len(x)>100 for x in self.value.get('values',[])):
                raise ValueError('Expected short selections')
        if self.step == 4:
            low, high = self.value.get('min',0),self.value.get('max',100)
            if not isinstance(low,(int,float)) or not isinstance(high,(int,float)) or not 0 <= low <= high <= 10000:
                raise ValueError('Invalid budget range')
            if self.value.get('unit','couple') not in ('couple','person'):
                raise ValueError('Invalid budget unit')
        if self.step == 5 and any(not isinstance(v,(int,float)) or not 0 <= v <= 1 for v in self.value.values()):
            raise ValueError('Style sliders must be between 0 and 1')
        if self.step == 6:
            if not isinstance(self.value.get('travel_minutes',60),(int,float)) or not 0 <= self.value.get('travel_minutes',60) <= 480:
                raise ValueError('Invalid travel time')
            for key in ('days','dietary','accessibility'):
                if not isinstance(self.value.get(key,[]),list) or any(not isinstance(x,str) or len(x)>100 for x in self.value.get(key,[])):
                    raise ValueError('Practical selections must be lists')
        if self.step == 7:
            if not isinstance(self.value.get('text',''),str):
                raise ValueError('Experience must be text')
            if 'privacy_scope' not in self.model_fields_set:
                self.privacy_scope = 'PRIVATE'
        return self

class OnboardingService:
    def __init__(self, db, memory):
        self.db, self.memory = db, memory
        self.lock = RLock()

    def create(self, request):
        cid = uuid4().hex
        members = []
        with self.db.connect() as c:
            c.execute('INSERT INTO v2_couples(id,created_at) VALUES(?,?)',(cid,now()))
            for role,name in [('A',request.person_a.strip()),('B',request.person_b.strip())]:
                if not name:
                    raise ValueError('Name is required')
                uid,token = uuid4().hex,secrets.token_urlsafe(32)
                c.execute('INSERT INTO v2_users VALUES(?,?,?)',(uid,name,sha256(token.encode()).hexdigest()))
                c.execute('INSERT INTO v2_memberships(couple_id,user_id,role) VALUES(?,?,?)',(cid,uid,role))
                members.append({'id':uid,'name':name,'role':role,'token':token})
        return {'couple_id':cid,'members':members,'status':self.status(cid)}

    def authenticate(self, token):
        if not token:
            raise PermissionError('Member token required')
        with self.db.connect() as c:
            row = c.execute('SELECT u.id,u.name,m.couple_id,m.role FROM v2_users u JOIN v2_memberships m ON m.user_id=u.id WHERE u.token_hash=?',(sha256(token.encode()).hexdigest(),)).fetchone()
        if row is None:
            raise PermissionError('Invalid member token')
        return dict(row)

    def status(self,cid):
        with self.db.connect() as c:
            couple = c.execute('SELECT * FROM v2_couples WHERE id=?',(cid,)).fetchone()
            if couple is None:
                raise KeyError('Unknown couple')
            members = [dict(r) for r in c.execute('SELECT u.id,u.name,m.role,m.status,m.current_step,m.completed_at FROM v2_memberships m JOIN v2_users u ON u.id=m.user_id WHERE m.couple_id=? ORDER BY m.role',(cid,))]
        return {'couple_id':cid,'status':couple['onboarding_status'],'completed':couple['onboarding_status']=='completed','members':members,'profile_version':couple['profile_version']}

    def authorize(self,cid,uid,viewer):
        if viewer['id'] != uid or viewer['couple_id'] != cid:
            raise PermissionError('This interview belongs to another person')

    def member(self,cid,uid,viewer):
        self.authorize(cid,uid,viewer)
        with self.db.connect() as c:
            answers = [{'step':r['step'],'value':json.loads(r['payload']),'privacy_scope':r['privacy_scope']} for r in c.execute('SELECT * FROM v2_answers WHERE user_id=? ORDER BY step',(uid,))]
        member = next(m for m in self.status(cid)['members'] if m['id']==uid)
        return {**member,'answers':answers}

    def answer(self,cid,uid,viewer,answer):
        self.authorize(cid,uid,viewer)
        with self.lock:
            payload = encoded(answer.value)
            with self.db.connect() as c:
                old = c.execute('SELECT * FROM v2_answers WHERE user_id=? AND step=?',(uid,answer.step)).fetchone()
            if old and old['payload']==payload and old['privacy_scope']==answer.privacy_scope:
                return self.member(cid,uid,viewer)
            category = ['identity','interests','dislikes','budget','style','practical','experience'][answer.step-1]
            existing = [f for f in self.memory.list_facts(cid,'PERSON',uid,uid) if f['key']==f'onboarding:{answer.step}']
            fact = self.memory.ingest(couple_id=cid,scope='PERSON',entity_id=uid,owner_id=uid,category=category,key=f'onboarding:{answer.step}',value=answer.value,privacy_scope=answer.privacy_scope,source='onboarding',idempotency_key='answer:'+uid+':'+str(answer.step)+':'+sha256((payload+answer.privacy_scope+(old['updated_at'] if old else 'initial')).encode()).hexdigest(),supersedes=existing[0]['id'] if existing else None)
            with self.db.connect() as c:
                c.execute('INSERT INTO v2_answers VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,step) DO UPDATE SET payload=excluded.payload,privacy_scope=excluded.privacy_scope,updated_at=excluded.updated_at',(cid,uid,answer.step,payload,answer.privacy_scope,now()))
                steps = {r[0] for r in c.execute('SELECT step FROM v2_answers WHERE user_id=?',(uid,))}
                next_step = next((x for x in range(1,8) if x not in steps),7)
                c.execute("UPDATE v2_memberships SET current_step=?,status=CASE WHEN status='completed' THEN status ELSE 'in_progress' END WHERE user_id=?",(next_step,uid))
            if self.status(cid)['completed']:
                self.memory.derive_couple(cid)
            return self.member(cid,uid,viewer)

    def complete(self,cid,uid,viewer):
        self.authorize(cid,uid,viewer)
        with self.lock:
            if self.status(cid)['completed']:
                return self.status(cid)
            with self.db.connect() as c:
                count=c.execute('SELECT COUNT(*) FROM v2_answers WHERE user_id=?',(uid,)).fetchone()[0]
                if count != 7:
                    raise ValueError('Answer or skip all seven steps before completing')
                c.execute("UPDATE v2_memberships SET status='completed',completed_at=COALESCE(completed_at,?),current_step=7 WHERE user_id=?",(now(),uid))
                remaining=c.execute("SELECT COUNT(*) FROM v2_memberships WHERE couple_id=? AND status!='completed'",(cid,)).fetchone()[0]
            if not remaining:
                self.memory.derive_couple(cid)
                with self.db.connect() as c:
                    c.execute("UPDATE v2_couples SET onboarding_status='completed' WHERE id=?",(cid,))
            return self.status(cid)
