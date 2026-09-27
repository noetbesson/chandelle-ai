"""Thin authenticated aliases into the existing E planning service, not another backend."""
from fastapi import APIRouter, Depends
from backend.integrations.calendar.store import calendar_locked
from backend.streams.E_orchestrator.service import Query
from backend.streams.E_orchestrator.deck_models import (
    DateSearch,DateSearchResponse,ActivityReplacement,DateComposition,DeckPlan,
)


def install_date_routes(app,planning,ready):
    router=APIRouter()

    @router.post('/search',response_model=DateSearchResponse)
    def search(body:DateSearch,member=Depends(ready)):
        if body.couple_id is not None and body.couple_id!=member['couple_id']:
            raise PermissionError('Ce couple ne correspond pas au profil connecté.')
        request=Query.model_validate(body.constraints.model_dump())
        request.max_plans=3
        result=planning.query(member['couple_id'],request,deck_options={
            'owner_id':member['id'],'duration':body.constraints.max_total_duration_minutes,
            'travel':body.constraints.max_travel_time_minutes})
        return {'search_id':result['run_id'],'proposals':result['plans'],
                'warnings':result['warnings'],'composition':result['composition'],
                **{k:result.get(k) for k in ('status','empty_reason','message','trace','sources','searched_at','cached') if k in result},
                **{k:result[k] for k in ('activities','budget_cap','max_total_duration_minutes','max_travel_time_minutes','requested_steps')}}

    @router.post('/{pid}/replace-activity',response_model=DeckPlan)
    @calendar_locked
    def replace(pid:str,body:ActivityReplacement,member=Depends(ready)):
        plan=planning.get(member['couple_id'],pid)
        if '_deck' not in plan:raise ValueError('Relancez une recherche de trois programmes avant ce remplacement.')
        return planning.replace(member['couple_id'],pid,body.activity_id_to_replace,body.new_constraints)

    @router.post('/compose',response_model=DeckPlan)
    @calendar_locked
    def compose(body:DateComposition,member=Depends(ready)):
        return planning.compose(member['couple_id'],member['id'],body.selected_activity_ids,body.search_id)

    app.include_router(router,prefix='/api/dates',tags=['Date proposals'])
    app.include_router(router,prefix='/api/v2/dates',include_in_schema=False)
