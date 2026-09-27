"""Edits use the existing plan store and the saved pool, with fresh hard-constraint checks."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from backend.integrations.openai import OpenAIAdapter
from backend.streams.A_calendar.service import AvailabilityService
from backend.streams.H_conversation.service import interests, normalize
from .date_composer import candidate_plans, describe_plan
from .models import CandidateActivity, DatePlan, PlanRequest, TimeWindow
from .planner import _prepare, _compatible


def refresh_pool(planning, cid: str, item: dict) -> tuple[list[dict], TimeWindow, float]:
    """No external search. Revalidate saved IDs against the current local catalogue and B/A."""
    window = TimeWindow.model_validate(item['time_window'])
    deck = item['_deck']
    if (datetime.now(timezone.utc)-datetime.fromisoformat(deck.get('created_at',item['generated_at']).replace('Z','+00:00'))).total_seconds()>86400:
        raise ValueError('Cette recherche a plus de 24 h. Relancez-la pour vérifier les disponibilités.')
    available = AvailabilityService(planning.db).windows(cid,window)
    if not any(w.start <= window.start and w.end >= window.end for w in available):
        raise ValueError('Les disponibilités ont changé. Relancez la recherche.')
    caps=[item['budget_cap']] if item['budget_cap'] is not None else []
    for profile in planning.memory.planning_context(cid).values():
        if not isinstance(profile,dict):continue
        value=profile.get('budget')
        if isinstance(value,(int,float)):caps.append(value)
        elif isinstance(value,dict) and not value.get('flexible') and value.get('max') is not None:
            caps.append(value['max']*(2 if value.get('unit')=='person' else 1))
    budget=min(caps) if caps else 10000
    saved={row['activity']['id']:row for row in deck['pool']}
    current=planning.catalog.discover(cid,window,budget,radius_km=deck.get('radius_km'),limit=100,candidate_ids=set(saved))
    valid=[]
    for row in current:
        old=saved[row['activity']['id']]
        # A price/time/location change invalidates the snapshot, never silently changes another step.
        if any(row['candidate'].get(k)!=old['candidate'].get(k) for k in ('start','end','price_per_person','location','type','name','booking_url')):
            continue
        valid.append(old)
    return valid,window,budget


def replacement_filter(rows: list[dict], text: str | None) -> list[dict]:
    if not text or not text.strip():return rows
    normalized=normalize(text)
    positive,negative=interests(text)
    amount=re.search(r'(?:moins de|under|max(?:imum)?|budget)\s*(?:de|of)?\s*(\d+(?:[.,]\d+)?)|\b(\d+(?:[.,]\d+)?)\s*(?:€|euros?|eur)',normalized)
    cap=float(next(g for g in amount.groups() if g is not None).replace(',','.')) if amount else None
    for_two=bool(re.search(r'pour (?:deux|2)|a deux|total|couple|for two',normalized))
    if not positive and not negative and cap is None:
        raise ValueError('Précisez une catégorie, un goût (japonais, calme, jazz...) ou un prix en euros. Aucun filtre reconnu.')
    def matches(row):
        terms=normalize(' '.join([row['candidate']['type'],row['candidate']['name'],*row['candidate']['tags']]))
        # Tags use the canonical B/H vocabulary, never execute instructions from text.
        return (all(tag in terms for tag in positive) and not any(tag in terms for tag in negative)
                and (cap is None or row['candidate']['price_per_person']*(2 if for_two else 1)<=cap))
    return [row for row in rows if matches(row)]


def build(planning,cid,item,rows,window,budget,steps,required,*,fixed=False):
    request=PlanRequest(time_window=window,couple_profile=planning._profile(planning.memory.planning_context(cid),budget),
                        candidate_activities=[CandidateActivity.model_validate(row['candidate']) for row in rows])
    if steps>3 and not fixed:
        # One replacement at a time; avoid combinatorial generation for long hand-made dates.
        plans=[]
        for row in sorted(rows,key=lambda r:-r['couple_score']):
            if row['activity']['id'] in required:continue
            chosen=set(required)|{row['activity']['id']}
            trial=request.model_copy(update={'candidate_activities':[a for a in request.candidate_activities if a.id in chosen]})
            plans,_=candidate_plans(trial,steps,item['_deck']['duration'],item['_deck']['travel'],chosen,fixed_selection=True)
            if plans:break
    else:
        plans,_=candidate_plans(request,steps,item['_deck']['duration'],item['_deck']['travel'],set(required),fixed_selection=fixed)
    if not plans:
        raise ValueError('Ces activités ne peuvent pas s’enchaîner dans ce créneau avec ce budget et ces trajets. Votre programme est conservé.')
    plan=plans[0]
    by_id={row['activity']['id']:row for row in rows}
    result=planning._decorate(plan,[by_id[a.id] for a in plan.activities],cid,'offline',window,budget)
    label,reason=describe_plan(plan)
    result.update(diversity_label=label,reason=reason,duration_minutes=round((plan.end-plan.start).total_seconds()/60),search_id=item['_deck']['search_id'])
    result['_deck']=item['_deck']
    # Optional short explanation uses the already budgeted adapter and public catalogue facts only.
    if item['_deck'].get('cloud_consent') or item['_deck'].get('processing_standard'):
        import os
        if os.getenv('OPENAI_PLAN_EXPLANATIONS')=='1':
            adapter=OpenAIAdapter(db=planning.db)
            explanation=adapter.explain([{'id':a.id,'title':a.name} for a in plan.activities])
            if adapter.last_mode=='openai':result.update(reason=explanation.explanation,mode='openai')
    return result


def replace_activity(planning,cid,item,activity_id,text=None):
    old={a['id']:a for a in item['activities']}
    if activity_id not in old:raise ValueError('Activité absente du programme.')
    rows,window,budget=refresh_pool(planning,cid,item)
    kept=set(old)-{activity_id}
    allowed={r['activity']['id'] for r in rows}
    if not kept<=allowed:raise ValueError('Une étape conservée ne respecte plus les contraintes actuelles. Relancez la recherche.')
    choices=replacement_filter([r for r in rows if r['activity']['id'] not in old],text)
    request=PlanRequest(time_window=window,couple_profile=planning._profile(planning.memory.planning_context(cid),budget),
                        candidate_activities=[CandidateActivity.model_validate(r['candidate']) for r in rows])
    slots,_,_=_prepare(request)
    positions={s.activity.id:s for s in slots}
    sequence=list(old);index=sequence.index(activity_id)
    left=positions.get(sequence[index-1]) if index else None
    right=positions.get(sequence[index+1]) if index<len(sequence)-1 else None
    # Keep the replaced step BETWEEN its original neighbours, including across midnight.
    choices=[r for r in choices if (s:=positions.get(r['activity']['id'])) is not None
             and (left is None or _compatible(left,s)) and (right is None or _compatible(s,right))]
    candidates=[r for r in rows if r['activity']['id'] in kept]+choices
    result=build(planning,cid,item,candidates,window,budget,len(old),kept)
    # Preserve the COMPLETE untouched activity payload, not merely its name and ID.
    result['activities']=[old[a['id']] if a['id'] in kept else a for a in result['activities']]
    base=DatePlan.model_validate(result['_e_plan'])
    previous=DatePlan.model_validate(item['_e_plan'])
    preserved={a.id:a for a in previous.activities if a.id in kept}
    base.activities=[preserved.get(a.id,a) for a in base.activities]
    result['_e_plan']=base.model_dump(mode='json')
    result.update(id=item['id'],date_plan_id=item['id'],kept_ids=item['kept_ids'],status=item['status'],generated_at=item['generated_at'])
    planning.save(result)
    return planning.public(result)


def compose_selection(planning,cid,uid,selected_ids,search_id=None):
    if len(set(selected_ids))!=len(selected_ids):raise ValueError('Sélection dupliquée.')
    # Scope to an authenticated person's search, never accept a foreign pool/plan identifier.
    with planning.db.connect() as c:
        records=c.execute('SELECT payload FROM v2_plans WHERE couple_id=? ORDER BY created_at DESC',(cid,)).fetchall()
    source=None
    for record in records:
        item=json.loads(record[0]);deck=item.get('_deck',{})
        if deck.get('owner_id')==uid and (search_id is None or deck.get('search_id')==search_id):
            source=item;break
    if source is None and search_id:
        with planning.db.connect() as c:
            record=c.execute('SELECT payload FROM v2_runs WHERE id=? AND couple_id=?',(search_id,cid)).fetchone()
        snapshot=json.loads(record[0]).get('_activity_search') if record else None
        if snapshot and snapshot['_deck']['owner_id']==uid:source=snapshot
    if source is None:raise KeyError('Recherche inconnue pour ce profil.')
    rows,window,budget=refresh_pool(planning,cid,source)
    allowed={r['activity']['id'] for r in rows}
    if not set(selected_ids)<=allowed:raise ValueError('Une sélection n’appartient plus à cette recherche. Relancez-la.')
    result=build(planning,cid,source,[r for r in rows if r['activity']['id'] in selected_ids],window,budget,len(selected_ids),selected_ids,fixed=True)
    planning.save(result)
    return planning.public(result)
