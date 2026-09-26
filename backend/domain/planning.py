"""V2 B → C → verified E composition, durable plans and outcome learning."""
from datetime import datetime
from uuid import uuid4
import json
from pydantic import BaseModel, Field
from typing import Literal
from backend.domain.onboarding import now, encoded, Privacy
from backend.integrations.openai import OpenAIAdapter
from backend.streams.E_orchestrator.models import CandidateActivity, CoupleProfile, PersonPreferences, PlanRequest, TimeWindow, ReplaceRequest, DatePlan
from backend.streams.E_orchestrator.planner import generate, replace, _distance_minutes, Slot
from backend.streams.H_conversation.service import default_availability

class Query(BaseModel):
    text: str = Field(default='A date for us',min_length=1,max_length=2000)
    budget: float | None = Field(default=None,ge=0,le=10000)
    categories: list[str] = Field(default_factory=list)
    required_activity_id: str | None = None
    radius_km: float | None = Field(default=None,ge=0,le=200)
    activity_count: int = Field(default=3,ge=1,le=3)
    max_plans: int = Field(default=3,ge=1,le=3)
    mode: Literal['offline','openai'] = 'offline'
    time_window: TimeWindow | None = None

class Review(BaseModel):
    rating: int = Field(ge=1,le=5)
    activity_ratings: dict[str,int] = Field(default_factory=dict)
    text: str = Field(default='',max_length=4000)
    repeat: list[str] = Field(default_factory=list,max_length=20)
    avoid: list[str] = Field(default_factory=list,max_length=20)
    privacy_scope: Privacy = 'PRIVATE'
    idempotency_key: str = Field(min_length=1,max_length=100)

class PlanningService:
    def __init__(self,db,memory,catalog):
        self.db,self.memory,self.catalog=db,memory,catalog

    def _profile(self,context,budget):
        a,b=context['person_a'],context['person_b']
        couple=context['couple']
        return CoupleProfile(user_a=PersonPreferences(interests=a.get('interests',[]),dislikes=a.get('dislikes',[])),user_b=PersonPreferences(interests=b.get('interests',[]),dislikes=b.get('dislikes',[])),shared_interests=couple.get('interests',couple.get('shared_interests',[])),dislikes=list(set(a.get('dislikes',[])+b.get('dislikes',[]))),typical_budget=budget,desired_novelty=couple.get('novelty',.5))

    def query(self,cid,request):
        rid=uuid4().hex
        trace=[]
        try:
            adapter=OpenAIAdapter(enabled=request.mode=='openai' and OpenAIAdapter().enabled)
            parsed=adapter.parse(request.text)
            trace.append({'stage':'parse','detail':'Validated request and explicit constraints','mode':adapter.last_mode})
            context=self.memory.planning_context(cid)
            trace.append({'stage':'memories','detail':'Loaded separately consent-filtered Person A, Person B and Couple context'})
            window=request.time_window or default_availability()
            budget=request.budget if request.budget is not None else parsed.budget
            # Persisted budgets also cap the complete plan, not only single candidates.
            limits=[budget] if budget is not None else []
            for profile in (context['person_a'],context['person_b'],context['couple']):
                value=profile.get('budget')
                if isinstance(value,(int,float)):
                    limits.append(value)
                elif isinstance(value,dict) and not value.get('flexible') and value.get('max') is not None:
                    limits.append(value['max']*(2 if value.get('unit')=='person' else 1))
            budget=min(limits) if limits else 150
            scored=self.catalog.discover(cid,window,budget,request.categories or parsed.categories,request.radius_km,query=request.text)
            if parsed.excluded:
                scored=[x for x in scored if not any(t.lower() in (x['activity']['category']+' '+' '.join(x['activity']['tags'])).lower().split() for t in parsed.excluded)]
            candidates=[CandidateActivity.model_validate(x['candidate']) for x in scored]
            trace.append({'stage':'candidates','detail':f'{len(candidates)} catalog activities pass hard constraints'})
            profile=self._profile(context,budget)
            # E's public V1 contract allows four stops; constrain V2 search explicitly.
            plans,rejected=generate(PlanRequest(time_window=window,couple_profile=profile,candidate_activities=candidates,max_plans=3),max_activities=request.activity_count,must_include={request.required_activity_id} if request.required_activity_id else None)
            mode=adapter.last_mode
            result=[]
            for plan in plans[:request.max_plans]:
                selected=[next(x for x in scored if x['activity']['id']==a.id) for a in plan.activities]
                explanation=adapter.explain([{'id':x['activity']['id'],'title':x['activity']['title'],'person_a_score':x['person_a_score'],'person_b_score':x['person_b_score']} for x in selected]) if request.mode=='openai' else None
                if adapter.last_mode=='openai':mode='openai'
                item=self._decorate(plan,selected,cid,mode,window,budget)
                if explanation is not None:item['reason']=explanation.explanation
                item['_candidates']=[x.model_dump(mode='json') for x in candidates]
                item['_profile']=profile.model_dump(mode='json')
                self.save(item)
                result.append(self.public(item))
            trace.append({'stage':'plan','detail':f'{len(result)} coherent plans composed by E'})
            output={'run_id':rid,'plans':result,'trace':trace,'mode':mode,'status':'completed'}
            self._run(cid,rid,output)
            return output
        except Exception:
            self._run(cid,rid,{'run_id':rid,'status':'failed','trace':trace,'error':'No feasible plan or invalid request'})
            raise

    def _run(self,cid,rid,payload):
        with self.db.connect() as c:c.execute('INSERT INTO v2_runs VALUES(?,?,?,?)',(rid,cid,encoded(payload),now()))

    def _decorate(self,plan,selected,cid,mode,window,budget):
        item=plan.model_dump(mode='json')
        item['id']=item['date_plan_id']=uuid4().hex
        item.update(couple_id=cid,status='draft',generated_at=now(),mode=mode,model=OpenAIAdapter().model if mode=='openai' else None,source='internal_demo_unverified',kept_ids=[],total_couple_cost=plan.estimated_total_eur,per_person_cost=plan.estimated_total_eur/2,evidence=[e for x in selected for e in x['evidence']],time_window=window.model_dump(mode='json'),budget_cap=budget)
        for key in ('person_a_score','person_b_score','couple_score'):item[key]=round(sum(x[key] for x in selected)/len(selected),4)
        timeline=[]
        for i,a in enumerate(item['activities']):
            catalog=selected[i]['activity']
            a.update(title=a['name'],category=a['type'],source=catalog['source'],demo=True,description=catalog['description'],address=catalog['address'])
            if i:
                left,right=plan.activities[i-1],plan.activities[i]
                fake=lambda p:Slot(CandidateActivity(**p.model_dump(exclude={'why'})),plan.start,plan.end,0,0,0)
                minutes=round(_distance_minutes(fake(left),fake(right)))
                timeline.append({'type':'travel','minutes':minutes,'from':left.name,'to':right.name})
            timeline.append({'type':'activity','id':a['id'],'title':a['title'],'start':a['start'],'end':a['end']})
        item['timeline']=timeline
        item['_e_plan']=plan.model_dump(mode='json')
        return item

    def public(self,item):return {k:v for k,v in item.items() if not k.startswith('_')}

    def save(self,item):
        item={k:v for k,v in item.items() if k not in ('reviews','photos')}
        with self.db.connect() as c:c.execute('INSERT INTO v2_plans VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,payload=excluded.payload,updated_at=excluded.updated_at',(item['id'],item['couple_id'],item['status'],encoded(item),item['generated_at'],now()))

    def get(self,cid,pid,viewer_id=None):
        with self.db.connect() as c:
            row=c.execute('SELECT payload FROM v2_plans WHERE id=? AND couple_id=?',(pid,cid)).fetchone()
            if row is None:raise KeyError('Unknown plan')
            item=json.loads(row[0])
            reviews=[]
            for r in c.execute('SELECT * FROM v2_reviews WHERE plan_id=?',(pid,)):
                payload=json.loads(r['payload'])
                if r['user_id']==viewer_id or payload['privacy_scope']=='SHARED':reviews.append({**payload,'id':r['id'],'user_id':r['user_id']})
            item['reviews']=reviews
            item['photos']=[dict(r) for r in c.execute('SELECT id,mime,size,created_at,user_id FROM v2_uploads WHERE plan_id=? AND user_id=?',(pid,viewer_id))]
        return item

    def list(self,cid,history=False):
        with self.db.connect() as c:
            rows=c.execute('SELECT payload FROM v2_plans WHERE couple_id=? ORDER BY created_at DESC',(cid,)).fetchall()
        items=[self.public(json.loads(r[0])) for r in rows if not history or json.loads(r[0])['status'] in ('accepted','completed','cancelled')]
        return {'items':items,'total':len(items)}

    def change(self,cid,pid,status=None,kept_ids=None):
        item=self.get(cid,pid)
        if status:
            transitions={'draft':{'proposed','accepted','cancelled'},'proposed':{'accepted','cancelled'},'accepted':{'completed','cancelled'},'completed':set(),'cancelled':set()}
            if status!=item['status'] and status not in transitions[item['status']]:raise ValueError('Invalid plan status transition')
            item['status']=status
        if kept_ids is not None:
            if not set(kept_ids).issubset({a['id'] for a in item['activities']}):raise ValueError('Unknown kept activity')
            item['kept_ids']=list(set(kept_ids))
        self.save(item)
        if item['status']=='completed':self._record_history(item)
        return self.public(item)

    def _record_history(self,item):
        with self.db.connect() as c:members=[r[0] for r in c.execute('SELECT user_id FROM v2_memberships WHERE couple_id=?',(item['couple_id'],))]
        for uid in members:
            self.memory.ingest(item['couple_id'],'DATE',item['id'],uid,'history','completed-plan',{'activity_ids':[a['id'] for a in item['activities']], 'status':'completed'},'SHARED','date_history',idempotency_key='completed:'+item['id']+':'+uid)

    def replace(self,cid,pid,activity_id):
        item=self.get(cid,pid)
        if item['status'] not in ('draft','proposed'):raise ValueError('Only draft or proposed plans can change')
        if activity_id in item['kept_ids']:raise ValueError('Unkeep this activity before replacing it')
        window=TimeWindow.model_validate(item['time_window'])
        context=self.memory.planning_context(cid)
        caps=[item['budget_cap']]
        for profile in (context['person_a'],context['person_b'],context['couple']):
            value=profile.get('budget',{})
            if isinstance(value,dict) and not value.get('flexible') and value.get('max') is not None:caps.append(value['max']*(2 if value.get('unit')=='person' else 1))
        item['budget_cap']=min(caps)
        current=self.catalog.discover(cid,window,item['budget_cap'])
        allowed={x['activity']['id']:x for x in current}
        old=DatePlan.model_validate(item['_e_plan'])
        if any(a.id not in allowed for a in old.activities if a.id!=activity_id):raise ValueError('Kept activity no longer satisfies current constraints')
        # Preserve kept source snapshots while applying current hard exclusions.
        preserved={a.id:a for a in old.activities if a.id!=activity_id}
        candidates=[]
        for x in current:
            candidate=CandidateActivity.model_validate(x['candidate'])
            if candidate.id in preserved:
                candidate=CandidateActivity(**preserved[candidate.id].model_dump(exclude={'why'}))
            candidates.append(candidate)
        plans,_=replace(ReplaceRequest(time_window=window,couple_profile=self._profile(self.memory.planning_context(cid),item['budget_cap']),candidate_activities=candidates,plan=old,replace_activity_id=activity_id,max_plans=1))
        new=self._decorate(plans[0],[allowed[a.id] for a in plans[0].activities],cid,'offline',window,item['budget_cap'])
        new.update(id=pid,date_plan_id=pid,kept_ids=item['kept_ids'],status=item['status'],generated_at=item['generated_at'])
        new['reason']='Replacement preserves the other activities and fits current constraints, travel and budget.'
        self.save(new)
        return self.public(new)

    def review(self,cid,pid,uid,review):
        item=self.get(cid,pid,uid)
        if item['status'] not in ('accepted','completed'):raise ValueError('Accept the plan before reviewing')
        if not set(review.activity_ratings).issubset({x['id'] for x in item['activities']}) or any(not 1<=v<=5 for v in review.activity_ratings.values()):raise ValueError('Invalid activity ratings')
        key=f'{uid}:{pid}:{review.idempotency_key}'
        with self.db.connect() as c:
            prior=c.execute('SELECT payload FROM v2_reviews WHERE idempotency_key=?',(key,)).fetchone()
        if prior:
            if json.loads(prior[0])!=review.model_dump():raise ValueError('Idempotency key already used with different review')
            return self.public(item)
        normalize=lambda values:[next((a['type'] for a in item['activities'] if a['id']==value),value) for value in values]
        for category,values in [('interests',normalize(review.repeat)),('dislikes',normalize(review.avoid))]:
            if values:self.memory.ingest(cid,'PERSON',uid,uid,category,f'review:{pid}:{category}',{'values':values},review.privacy_scope,'review',idempotency_key=key+category)
        self.memory.ingest(cid,'DATE',pid,uid,'review',key,review.model_dump(),review.privacy_scope,'review',idempotency_key=key)
        with self.db.connect() as c:c.execute('INSERT INTO v2_reviews VALUES(?,?,?,?,?,?)',(uuid4().hex,pid,uid,encoded(review.model_dump()),now(),key))
        item['status']='completed'
        self.save(item)
        self._record_history(item)
        self.memory.derive_couple(cid)
        return self.public(self.get(cid,pid,uid))
