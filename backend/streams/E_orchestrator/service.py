"""V2 B → C → verified E composition, durable plans and outcome learning."""
from datetime import datetime
from uuid import uuid4
import json
import os
import logging
from backend.streams.E_orchestrator.activity_choices import activity_choices, search_snapshot
from backend.streams.E_orchestrator.date_composer import candidate_plans, describe_plan
from backend.integrations.date_scoring import score as score_date_candidates
from backend.streams.E_orchestrator.date_intent import date_intent,matches_requested_tags
from pydantic import BaseModel, Field
from typing import Literal
from backend.db import now, encoded
from backend.streams.B_memory.service import Privacy
from backend.integrations.openai import OpenAIAdapter
from backend.streams.E_orchestrator.models import CandidateActivity, CoupleProfile, PersonPreferences, PlanRequest, TimeWindow, ReplaceRequest, DatePlan
from backend.streams.E_orchestrator.planner import generate, replace, _distance_minutes, Slot
from backend.streams.A_calendar.service import AvailabilityService
from backend.streams.E_orchestrator.planner import NoFeasiblePlan

class PlanningIssue(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def calendar_issue(availability, cid, requested):
    rows = availability._rows(cid)
    if len(rows) == 1:
        return PlanningIssue('calendar_incomplete', 'Les disponibilités d’une personne manquent. Ajoutez-les dans « Nos disponibilités ». Je peux déjà proposer des idées sans fixer de date.')
    if rows and any(not slots for slots in rows.values()):
        return PlanningIssue('calendar_empty', 'Au moins un agenda ne contient aucun créneau libre enregistré. Ajoutez une disponibilité ou poursuivons avec des idées sans date.')
    if rows and not availability.common(cid):
        return PlanningIssue('calendar_no_overlap', 'Vos disponibilités enregistrées ne se recoupent pas. Choisissons un autre créneau ; les idées restent consultables.')
    if requested:
        return PlanningIssue('requested_time_unavailable', 'Le créneau demandé ne correspond pas à vos disponibilités communes enregistrées. Quel autre moment vous conviendrait ?')
    return PlanningIssue('calendar_expired', 'Les créneaux communs enregistrés sont passés. Actualisez vos disponibilités pour dater le programme.')


class Query(BaseModel):
    text: str = Field(default='A date for us',min_length=1,max_length=2000)
    budget: float | None = Field(default=None,ge=0,le=10000)
    categories: list[str] = Field(default_factory=list)
    required_activity_id: str | None = None
    required_activity_ids: list[str] = Field(default_factory=list,max_length=3)
    radius_km: float | None = Field(default=None,ge=0,le=200)
    activity_count: int = Field(default=3,ge=1,le=3)
    max_plans: int = Field(default=3,ge=1,le=3)
    mode: Literal['offline','openai','auto'] = 'auto'
    use_shared_interests: bool = False
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

    def _query_candidates(self,cid,request,*,candidate_provider=None,parsed_request=None):
        rid=uuid4().hex
        trace=[]
        try:
            adapter=OpenAIAdapter(enabled=request.mode=='openai' and OpenAIAdapter().enabled,db=self.db)
            parsed=parsed_request if parsed_request is not None else adapter.parse(request.text)
            trace.append({'stage':'parse','detail':'Validated request and explicit constraints','mode':adapter.last_mode,'fallback':adapter.last_fallback})
            context=self.memory.planning_context(cid)
            trace.append({'stage':'memories','detail':'Loaded separately consent-filtered Person A, Person B and Couple context'})
            availability=AvailabilityService(self.db)
            try:
                windows=availability.windows(cid,request.time_window)
            except ValueError:
                raise calendar_issue(availability,cid,request.time_window) from None
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
            required=set(request.required_activity_ids)
            if request.required_activity_id:required.add(request.required_activity_id)
            if len(required)>request.activity_count:raise PlanningIssue('too_many_selected', 'Le nombre de choix dépasse le nombre d’activités demandé. Gardons moins d’activités ou augmentons ce nombre, jusqu’à trois.')
            profile=self._profile(context,budget)
            for window in windows:
                if window.start.utcoffset()!=window.end.utcoffset():
                    raise PlanningIssue('time_change', 'Choisissez un créneau sans changement d’heure pour composer ce programme.')
                scored=(candidate_provider(window,budget) if candidate_provider is not None else self.catalog.discover(cid,window,budget,request.categories or parsed.categories,request.radius_km,limit=100,query=request.text))
                if parsed.excluded:
                    from backend.streams.C_discovery.service import _matches, _normal
                    scored=[x for x in scored if not any(_matches(_normal(x['activity']['category']+' '+' '.join(x['activity']['tags'])),t) for t in parsed.excluded)]
                candidates=[CandidateActivity.model_validate(x['candidate']) for x in scored]
                try:
                    plans,rejected=generate(PlanRequest(time_window=window,couple_profile=profile,candidate_activities=candidates,max_plans=3),max_activities=request.activity_count,must_include=required or None)
                    break
                except NoFeasiblePlan:
                    continue
            else:raise PlanningIssue('no_feasible_activities', 'Le créneau existe, mais aucune combinaison d’activités ne respecte les horaires, trajets, choix et budget. Essayons une autre activité ou un autre créneau.')
            trace.append({'stage':'candidates','detail':f'{len(candidates)} catalog activities pass hard constraints','calendar_mode':'manual' if AvailabilityService(self.db)._rows(cid) else 'demo_or_requested','timezone':'Europe/Paris'})
            mode=adapter.last_mode
            result=[]
            for plan in plans[:request.max_plans]:
                selected=[next(x for x in scored if x['activity']['id']==a.id) for a in plan.activities]
                explanation=adapter.explain([{'id':x['activity']['id'],'title':x['activity']['title'],'person_a_score':x['person_a_score'],'person_b_score':x['person_b_score']} for x in selected]) if request.mode=='openai' and os.getenv('OPENAI_PLAN_EXPLANATIONS')=='1' else None
                if adapter.last_mode=='openai':mode='openai'
                item=self._decorate(plan,selected,cid,mode,window,budget)
                item['source']='real_source_availability_unconfirmed'
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

    def query(self,cid,request,*,deck_options=None,candidate_provider=None,parsed_request=None):
        if candidate_provider is not None:
            return self._query_candidates(cid,request,candidate_provider=candidate_provider,parsed_request=parsed_request)
        from datetime import timedelta,timezone
        from zoneinfo import ZoneInfo
        import hashlib
        import re
        from backend.streams.C_discovery.web import WebDiscovery,WebQuery,WebPlan
        from backend.streams.C_discovery.service import record_web,canonical_categories
        from backend.streams.C_discovery.local_catalog import ImportedCatalog, merge_sources
        from backend.streams.A_calendar.calendar_read import CalendarRead
        from backend.streams.A_calendar.service import paris_window
        rid=uuid4().hex
        options=dict(deck_options or {})
        if not options.get('owner_id'):
            with self.db.connect() as c:options['owner_id']=c.execute('SELECT user_id FROM v2_memberships WHERE couple_id=? ORDER BY role',(cid,)).fetchone()[0]
        options.setdefault('duration',360);options.setdefault('travel',30)
        trace=[{'stage':'request','request_hash':hashlib.sha256(request.text.encode()).hexdigest()[:16],'characters':len(request.text),'requested_steps':request.activity_count}]
        output={'run_id':rid,'plans':[],'activities':[],'trace':trace,'mode':'openai_web','status':'completed',
                'composition':{},'warnings':[],'empty_reason':None,'message':'','sources':[],
                'budget_cap':request.budget,'max_total_duration_minutes':options['duration'],
                'max_travel_time_minutes':options['travel'],'requested_steps':request.activity_count,
                '_owner_id':options['owner_id']}
        def finish():
            for step in trace:logging.getLogger('uvicorn.error').info('activity_search id=%s stage=%s metrics=%s',rid,step['stage'],json.dumps(step,ensure_ascii=True))
            self._run(cid,rid,output)
            return self.public(output)
        imported=ImportedCatalog(self.db)
        local=imported.search(request.text,canonical_categories(request.categories))
        if request.mode=='offline' and not local:
            output.update(status='unavailable',empty_reason='web_disabled',message='La recherche de sorties nécessite une connexion au service de recherche. Aucun catalogue de secours n’est utilisé.')
            trace.append({'stage':'web_search','before':0,'after':0,'reason':'offline_requested'})
            return finish()
        adapter=OpenAIAdapter(db=self.db)
        if request.mode=='offline':
            from backend.integrations.openai import ParsedRequest
            from backend.streams.H_conversation.service import parse_request
            parsed=ParsedRequest(**parse_request(request.text))
            adapter.last_mode='offline';adapter.last_fallback=None
        else:
            parsed=adapter.parse(request.text)
        categories=canonical_categories(request.categories or parsed.categories)
        categories,required_categories,category_order,requested_tags=date_intent(request.text,categories,request.activity_count)
        trace.append({'stage':'parse','mode':adapter.last_mode,'fallback':adapter.last_fallback,'categories':categories,'budget':request.budget if request.budget is not None else parsed.budget,'excluded_count':len(parsed.excluded)})
        local=imported.search(request.text,categories)
        if local:trace.append({'stage':'import_search','before':len(local),'after':len(local),'limit':80})
        if adapter.last_mode!='openai' and not local:
            output.update(status='unavailable',empty_reason=adapter.last_fallback or 'analysis_unavailable',message=self.search_error(adapter.last_fallback))
            return finish()
        # An unconfigured calendar is not a fictional Friday availability. This is a proposed search window.
        local_now=datetime.now(ZoneInfo('Europe/Paris'))
        requested=request.time_window
        if requested is None:
            date=getattr(parsed,'date',None)
            time=getattr(parsed,'time',None) or '18:00'
            start=datetime.fromisoformat((date or local_now.date().isoformat())+'T'+time).replace(tzinfo=ZoneInfo('Europe/Paris'))
            if not date and start<local_now:start=local_now.replace(second=0,microsecond=0)+timedelta(minutes=30)
            requested=TimeWindow(start=start,end=start+timedelta(minutes=options['duration']))
        window=paris_window(requested)
        availability=AvailabilityService(self.db)
        windows=[window]
        if availability._rows(cid) or CalendarRead(self.db).connected(cid):
            try:windows=availability.windows(cid,window)
            except ValueError:windows=[]
        trace.append({'stage':'calendar_window','before':1,'after':len(windows),'kind':'connected_or_manual' if availability._rows(cid) or CalendarRead(self.db).connected(cid) else 'proposed'})
        # Cards can still be browsed when no common slot is known; composition then remains unavailable.
        budget=request.budget if request.budget is not None else parsed.budget
        body=WebQuery(text=request.text,processing='standard',use_shared_interests=request.use_shared_interests,
            plan=WebPlan(budget=budget,date=window.start.date(),time=window.start.time().replace(tzinfo=None),
                         activity_count=request.activity_count,categories=categories,radius_km=request.radius_km or None,
                         time_window={'start':window.start.isoformat(),'end':window.end.isoformat()}))
        # Same pipeline and privacy filters for both sources. Do not pay to rediscover
        # a useful local shortlist unless dates/current information need checking.
        local_trace=[]
        local_ranked,_=self.catalog.filter_web(cid,local,window,budget,categories,request.radius_km,parsed.excluded,requested_tags,local_trace)
        if local:
            trace.extend({**t,'stage':'import_'+t['stage']} for t in local_trace)
        local=[r['activity'] for r in local_ranked]
        enough=len(local)>=3 and all(sum(a['category']==cat for a in local)>=3 for cat in categories)
        dated=bool(request.time_window or getattr(parsed,'date',None) or getattr(parsed,'time',None) or re.search(r'\b(ce soir|demain|aujourd|horaire|ouvert|disponib|seance|cette semaine|week.?end)\b',request.text,re.I))
        need_web=request.mode!='offline' and (not enough or dated)
        body.local_references=imported.shortlist(local)
        if not body.local_references and 'cinema' in categories:
            body.local_references=imported.shortlist(imported.search(request.text,['cinema'],8,references=True))
        if need_web:
            web=self.web.search({'id':options['owner_id'],'couple_id':cid},body) if hasattr(self,'web') else WebDiscovery(self.db,self.memory).search({'id':options['owner_id'],'couple_id':cid},body)
        else:
            web={'status':'completed','activities':[],'sources':[],'raw_count':0,'searched_at':None,'reason':'local_sufficient','tool_calls':0,'search_calls':0}
        output['mode']='hybrid' if local and need_web else 'imported_catalog' if local else 'openai_web'
        output['sources']=web.get('sources',[]);output['searched_at']=web.get('searched_at');output['cached']=web.get('cached',False)
        trace.append({'stage':'web_search','before':0,'after':web.get('raw_count',0),'cached':web.get('cached',False),'reason':web.get('reason'),'tool_calls':web.get('tool_calls'),'search_calls':web.get('search_calls'),'tool_limit':web.get('tool_limit'),'source_count':web.get('source_count'),'unknown_tool_actions':web.get('unknown_tool_actions')})
        trace.append({'stage':'schema_and_citations','before':web.get('raw_count',0),'after':len(web.get('activities',[])),'invalid':web.get('invalid_count',0),'uncited':web.get('uncited_count',0)})
        if web['status']!='completed' and not local:
            output.update(status='unavailable',empty_reason=web.get('reason'),message=self.search_error(web.get('reason')))
            return finish()
        if web['status']!='completed':
            output['warnings'].append('Les fiches importées restent disponibles. La vérification web est momentanément indisponible.')
        records=merge_sources(local,[record_web(v,web['searched_at']) for v in web.get('activities',[])])
        trace.append({'stage':'source_merge','before':len(local)+len(web.get('activities',[])),'after':len(records)})
        ranked,cap=self.catalog.filter_web(cid,records,window,budget,categories,request.radius_km,parsed.excluded,requested_tags,trace)
        output['budget_cap']=cap
        # Store sourced public records only. Recommendations/notes remain in the private run.
        self.catalog.persist([r['activity'] for r in ranked if r['activity'].get('provider')!='user_import'])
        from backend.streams.E_orchestrator.activity_choices import web_activity_choices
        output['activities']=web_activity_choices(ranked)
        planning_rows=[r for r in ranked if r['candidate'] is not None]
        if not windows:planning_rows=[]
        trace.append({'stage':'planning_fields','before':len(ranked),'after':len(planning_rows),'removed':len(ranked)-len(planning_rows)})
        plans=[];composition={};used_window=window;scored=planning_rows
        for allowed_window in windows:
            current=[r for r in planning_rows if datetime.fromisoformat(r['activity']['starts_at'])>=allowed_window.start and datetime.fromisoformat(r['activity']['ends_at'])<=allowed_window.end]
            if not current:continue
            current,backend,fallback=score_date_candidates(current,cap if cap is not None else 10000,request.radius_km or 10)
            plan_request=PlanRequest(time_window=allowed_window,couple_profile=self._profile(self.memory.planning_context(cid),cap),candidate_activities=[CandidateActivity.model_validate(r['candidate']) for r in current],max_plans=3)
            required=set(request.required_activity_ids)|({request.required_activity_id} if request.required_activity_id else set())
            plans,composition=candidate_plans(plan_request,request.activity_count,options['duration'],options['travel'],required,required_categories,category_order=category_order)
            composition.update(scoring_backend=backend,scoring_fallback=fallback)
            if plans:scored=current;used_window=allowed_window;break
        snapshot=search_snapshot(planning_rows,window,cap,rid,options,now(),request.radius_km)
        snapshot['_deck']['excluded']=parsed.excluded
        output['_activity_search']=snapshot
        for plan in plans[:3]:
            selected=[next(r for r in scored if r['activity']['id']==a.id) for a in plan.activities]
            item=self._decorate(plan,selected,cid,'openai_web',used_window,cap)
            label,reason=describe_plan(plan)
            item.update(diversity_label=label,reason=reason+' Disponibilité à confirmer auprès des lieux.',duration_minutes=round((plan.end-plan.start).total_seconds()/60),search_id=rid)
            item['_deck']=snapshot['_deck'];self.save(item);output['plans'].append(self.public(item))
        output['composition']=composition
        trace.append({'stage':'composition','before':len(planning_rows),'after':len(output['plans']),'combos_generated':composition.get('combos_generated',0)})
        if not ranked:
            reason='no_web_results' if web.get('raw_count',0)==0 and not any(t['stage']=='import_search' and t['after'] for t in trace) else 'all_filtered'
            output.update(empty_reason=reason,message='Aucune piste trouvée sur le web pour cette demande. Essayez d’autres mots ou une autre date.' if reason=='no_web_results' else 'Des pistes ont été trouvées, mais aucune ne respecte vos critères actuels ou ne dispose de sources suffisantes. Essayez d’élargir votre recherche.')
            last=next((t for t in trace if t.get('before',0)>0 and t.get('after')==0 and t.get('stage') not in ('planning_fields','composition','calendar_window')),None)
            labels={'region_idf':'localisation en Île-de-France','expiration':'dates expirées','category':'catégories demandées','budget':'budget','radius':'distance','availability':'indisponibilité annoncée','time_window':'créneau demandé','explicit_exclusions':'exclusions explicites','preferred_days':'jours autorisés','accessibility':'accessibilité documentée','dietary':'contraintes alimentaires','mobility_time':'durée de déplacement','requested_tags':'goûts demandés','schema_and_citations':'informations et sources vérifiables'}
            if last:output['message']+=f" Filtre bloquant : {labels.get(last['stage'].removeprefix('import_'),last['stage'])}."
        elif plans and len(plans)<3:
            output['warnings'].append(f'Seulement {len(plans)} programme(s) distinct(s) respectent ces critères.')
        elif not plans:
            output['warnings'].append('Les lieux ci-dessous sont des pistes sourcées. Aucun programme complet ne peut encore être composé : horaires, prix ou localisation manquants, ou contraintes incompatibles.')
            if not windows:output['warnings'].append('Les lieux restent consultables, mais aucun créneau commun ne permet de composer le programme. Vérifiez vos disponibilités.')
        missing=set(required_categories)-{r["activity"]["category"] for r in ranked}
        if ranked and missing:
            names={"food":"restaurant","outdoors":"balade","culture":"sortie culturelle","concerts":"concert","cinema":"cinéma"}
            output["warnings"].append("La recherche ne fournit pas encore de proposition pour : "+", ".join(names.get(c,c) for c in sorted(missing))+". Précisez ou relancez votre demande.")
        if output['message'] and not output['warnings']:output['warnings']=[output['message']]
        return finish()

    @staticmethod
    def search_error(reason):
        if reason=='invalid_search_configuration':return 'La configuration de recherche du serveur doit être corrigée.'
        if reason=='budget_limit_reached':return 'Le quota de recherche est atteint. Réessayez après sa remise à zéro ou contactez la personne qui gère Chandelle.'
        if reason=='provider_timeout':return 'La recherche a pris trop de temps. Réessayez dans un instant.'
        if reason=='provider_rate_limited':return 'Le service de recherche est momentanément saturé. Réessayez plus tard.'
        if reason in ('not_configured_or_disabled','authentication_failed'):return 'Le service de recherche est indisponible ou non configuré. La configuration du serveur doit être vérifiée.'
        return 'La recherche n’a pas fourni de résultat exploitable. Réessayez dans un instant.'

    def _activity_output(self,output,rows,window,budget,rid,request,options):
        plan_ids={a['id'] for p in output['plans'] for a in p['activities']}
        output.update(activities=activity_choices(rows,window,plan_ids) if window else [],budget_cap=budget,
            max_total_duration_minutes=options['duration'],max_travel_time_minutes=options['travel'],requested_steps=request.activity_count)
        if window:
            output['_activity_search']=search_snapshot(rows,window,budget,rid,options,now(),request.radius_km)

    def _run(self,cid,rid,payload):
        with self.db.connect() as c:c.execute('INSERT INTO v2_runs VALUES(?,?,?,?)',(rid,cid,encoded(payload),now()))

    def _decorate(self,plan,selected,cid,mode,window,budget):
        item=plan.model_dump(mode='json')
        item['id']=item['date_plan_id']=uuid4().hex
        item.update(couple_id=cid,status='draft',generated_at=now(),mode=mode,model=OpenAIAdapter().model if mode=='openai' else None,source='web_sourced_unverified_availability',kept_ids=[],total_couple_cost=plan.estimated_total_eur,per_person_cost=plan.estimated_total_eur/2,evidence=[e for x in selected for e in x['evidence']],time_window=window.model_dump(mode='json'),budget_cap=budget)
        for key in ('person_a_score','person_b_score','couple_score'):item[key]=round(sum(x[key] for x in selected)/len(selected),4)
        timeline=[]
        for i,a in enumerate(item['activities']):
            catalog=selected[i]['activity']
            a.update(title=a['name'],category=a['type'],source=catalog['source'],demo=False,description=catalog['description'],address=catalog['address'],source_url=catalog.get('source_url'),schedule_status=catalog.get('schedule_status'),checked_at=catalog.get('checked_at'))
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
        items=[self.public(json.loads(r[0])) for r in rows if (history and json.loads(r[0])['status'] in ('accepted','completed','cancelled')) or (not history and not any(a.get('demo') for a in json.loads(r[0]).get('activities',[])))]
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

    def replace(self,cid,pid,activity_id,new_constraints=None):
        item=self.get(cid,pid)
        if item['status'] not in ('draft','proposed'):raise ValueError('Only draft or proposed plans can change')
        if activity_id in item['kept_ids']:raise ValueError('Unkeep this activity before replacing it')
        if '_deck' in item:
            from backend.streams.E_orchestrator.deck_operations import replace_activity
            return replace_activity(self,cid,item,activity_id,new_constraints)
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

    def compose(self,cid,uid,selected_ids,search_id=None):
        from backend.streams.E_orchestrator.deck_operations import compose_selection
        return compose_selection(self,cid,uid,selected_ids,search_id)

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
