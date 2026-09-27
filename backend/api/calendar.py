"""Calendar and proactive routes use the existing member capability, including ownership checks."""
import hashlib
import logging
import secrets
from typing import Literal
from urllib.parse import parse_qs, urlsplit
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from backend.integrations.calendar.calendar_auth import CalendarAuth, callback_uri
from backend.integrations.calendar.provider import CalendarError
from backend.integrations.calendar.store import CalendarStore
from backend.streams.A_calendar.calendar_read import CalendarRead
from backend.streams.A_calendar.calendar_write import CalendarWrite
from backend.streams.G_proactive.notification_service import NotificationService
from backend.streams.G_proactive.scheduler import ProactiveScheduler

class Approval(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision: str=Field(pattern=r'^[a-f0-9]{64}$')

class Settings(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled: bool

class MoodConsent(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled: bool

class Trigger(BaseModel):
    model_config=ConfigDict(extra='forbid')
    demo: bool=False

class CallbackLogFilter(logging.Filter):
    def filter(self,record):
        if isinstance(record.args,tuple) and len(record.args)==5 and '/api/calendar/callback/' in str(record.args[2]):
            args=list(record.args);args[2]=str(args[2]).split('?')[0];record.args=tuple(args)
        return True

def install_calendar_routes(app,db,planning,suggestions,ready):
    auth=CalendarAuth(db);store=CalendarStore(db);read=CalendarRead(db);write=CalendarWrite(db,planning)
    notifications=NotificationService(db);scheduler=ProactiveScheduler(db,suggestions,read)
    app.state.calendars={'auth':auth,'store':store,'read':read,'write':write,'notifications':notifications,'scheduler':scheduler}
    if not any(isinstance(f,CallbackLogFilter) for f in logging.getLogger('uvicorn.access').filters):
        logging.getLogger('uvicorn.access').addFilter(CallbackLogFilter())
    app.router.add_event_handler('startup',scheduler.start)
    app.router.add_event_handler('shutdown',scheduler.stop)
    router=APIRouter(prefix='/api')

    @router.get('/calendar/connect/{provider}')
    @router.get('/v2/calendar/connect/{provider}')
    def connect(provider:Literal['google','outlook'],request:Request,format:Literal['json','redirect']='redirect',member=Depends(ready)):
        target=urlsplit(callback_uri(provider))
        if (request.url.scheme,request.url.netloc)!=(target.scheme,target.netloc):
            raise ValueError('CALENDAR_REDIRECT_BASE doit correspondre à l’adresse utilisée pour ouvrir Chandelle, même hôte et même port.')
        url=auth.begin(member['id'],provider)
        state=parse_qs(urlsplit(url).query)['state'][0]
        response=JSONResponse({'authorization_url':url}) if format=='json' else RedirectResponse(url,status_code=303)
        response.set_cookie('chandelle_calendar_oauth',hashlib.sha256(state.encode()).hexdigest(),
            httponly=True,secure=callback_uri(provider).startswith('https:'),samesite='lax',max_age=600,path='/api/calendar/callback')
        response.headers['Cache-Control']='no-store'
        return response

    @router.get('/calendar/callback/{provider}')
    def callback(provider:Literal['google','outlook'],request:Request):
        params=dict(request.query_params)
        state=params.get('state','')
        expected=hashlib.sha256(state.encode()).hexdigest()
        success=False
        if len(state)<=256 and secrets.compare_digest(expected,request.cookies.get('chandelle_calendar_oauth','')):
            try:auth.finish(provider,params);success=True
            except CalendarError:pass
        response=RedirectResponse('/app?calendar='+('connected' if success else 'failed'),status_code=303)
        response.delete_cookie('chandelle_calendar_oauth',path='/api/calendar/callback')
        response.headers.update({'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
        return response

    @router.get('/v2/calendar/status')
    def status(request:Request,member=Depends(ready)):
        return {**store.status(member['id']),'providers':{p:auth.configured(p) for p in ('google','outlook')},
            'apple':{'available':False,'alternative':'Export .ics existant ; CalDAV non implémenté.'},
            'window_policy':'Agenda principal uniquement. Sans créneaux manuels : 18 h à 23 h, Paris. Actualisation valable 15 minutes.'}

    @router.post('/v2/calendar/sync')
    def sync(member=Depends(ready)):return read.refresh(member['id'])

    @router.delete('/v2/calendar/connection')
    def disconnect(member=Depends(ready)):
        store.disconnect(member['id'])
        return {'connected':False,'message':'Accès local supprimé. Les événements déjà créés restent dans votre agenda.'}

    @router.get('/v2/calendar/plans/{pid}')
    def event_status(pid:str,member=Depends(ready)):return write.status(member,pid)

    @router.post('/v2/calendar/plans/{pid}/confirm')
    def confirm(pid:str,body:Approval,member=Depends(ready)):return write.confirm(member,pid,body.revision)

    @router.get('/v2/proactive/settings')
    def settings(member=Depends(ready)):
        with db.connect() as c:
            row=c.execute('SELECT enabled FROM v2_proactive_settings WHERE user_id=?',(member['id'],)).fetchone()
            cloud=c.execute('SELECT enabled FROM v2_mood_cloud WHERE user_id=?',(member['id'],)).fetchone()
            total=c.execute('SELECT COUNT(*) FROM v2_proactive_settings s JOIN v2_memberships m ON m.user_id=s.user_id WHERE m.couple_id=? AND s.enabled=1',(member['couple_id'],)).fetchone()[0]
        import os
        return {'enabled':bool(row and row[0]),'both_enabled':total==2,'scheduler':scheduler.status(member['couple_id']),
                'demo_available':os.getenv('CHANDELLE_DEV')=='1','cloud_mood':bool(cloud and cloud[0]),
                'cloud_mood_available':os.getenv('PROACTIVE_MOOD_OPENAI')=='1',
                'mood_mode':'Signaux récents autorisés. Sans indice : humeur neutre, confiance nulle. Analyse OpenAI facultative, au plus une tentative par jour et personne.'}

    @router.put('/v2/proactive/mood-consent')
    def mood_consent(body:MoodConsent,member=Depends(ready)):
        from backend.integrations.calendar.store import LOCK
        with LOCK,db.connect() as c:
            c.execute('INSERT INTO v2_mood_cloud VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled',(member['id'],int(body.enabled)))
            if not body.enabled:
                from backend.streams.G_proactive.mood_tracker import MoodSignal
                c.execute("UPDATE v2_mood_cache SET cache_key='',payload=? WHERE user_id=?",(MoodSignal(user_id=member['id']).model_dump_json(),member['id']))
        return settings(member)

    @router.put('/v2/proactive/settings')
    def set_settings(body:Settings,member=Depends(ready)):
        from backend.integrations.calendar.store import LOCK
        with LOCK,db.connect() as c:
            c.execute('INSERT INTO v2_proactive_settings VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled',(member['id'],int(body.enabled)))
            if not body.enabled:
                c.execute("UPDATE v2_suggestions SET state='expired' WHERE couple_id=? AND state IN ('new','viewed','snoozed') AND json_extract(payload,'$.source')='calendar_proactive'",(member['couple_id'],))
        return settings(member)

    @router.post('/proactive/trigger/{couple_id}')
    @router.post('/v2/proactive/trigger/{couple_id}')
    def trigger(couple_id:str,body:Trigger,member=Depends(ready)):
        if couple_id!=member['couple_id']:raise PermissionError('Autre couple.')
        return scheduler.run(couple_id,demo=body.demo)

    @router.get('/v2/notifications')
    def feed(member=Depends(ready)):return notifications.list(member)

    @router.post('/v2/notifications/{nid}/read')
    def mark_read(nid:str,member=Depends(ready)):return notifications.read(member,nid)

    app.include_router(router)
    return app.state.calendars
