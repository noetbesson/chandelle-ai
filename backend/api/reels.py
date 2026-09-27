"""Authenticated multipart entry point on the existing FastAPI application."""
from dataclasses import replace
import logging
import json
from pydantic import ValidationError
from backend.integrations.reels.models import TasteSignal
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from backend.api.reel_receive import receive, cleanup
from backend.integrations.reels.config import Settings
from backend.integrations.reels.errors import ReelError
from backend.integrations.reels.normalize_pipelex import select_backend
from backend.streams.B_memory.reels import ReelMemoryService

LOGGER=logging.getLogger(__name__)

def install_reel_routes(app, db, memory, ready):
    settings=replace(Settings.load(),work_dir=db.path.parent/'reels')
    service=ReelMemoryService(memory,settings)
    with db.connect() as c:
        interrupted=[row[0] for row in c.execute("SELECT id FROM v2_reel_jobs WHERE error='INTERRUPTED'")]
    for job_id in interrupted:
        cleanup(job_id,settings)
    app.state.v2['reels']=service
    router=APIRouter(prefix='/api/v2/reels')

    @app.exception_handler(ReelError)
    async def reel_error(request, error):
        return JSONResponse({'code':error.code,'message':error.message},status_code=error.status,headers={'Cache-Control':'no-store'})

    @router.get('/jobs/{job_id}')
    def status(job_id:str, member=Depends(ready)):
        return JSONResponse(service.status(job_id,member),headers={'Cache-Control':'no-store'})

    def process(received,member,config):
        try:
            return service.process(received,member,config)
        finally:
            cleanup(received.job_id,settings)

    def background(received,member,config):
        try: process(received,member,config)
        except ReelError as error: LOGGER.warning('reel_job_failed code=%s',error.code)

    @router.post('/upload')
    async def upload(request:Request, tasks:BackgroundTasks, wait:bool=False, member=Depends(ready)):
        received=await receive(request,settings)
        try:
            if received.share_with_couple:
                raise ReelError('CONSENT','Confirmez les goûts dans Inspirations avant de les partager.',422)
            config=replace(settings,allow_live=settings.allow_live and (received.cloud_consent or received.processing=='standard'))
            backend=select_backend(config)
            config=replace(config,normalization_backend=backend)
            existing=service.reserve(received,member,backend)
            if existing:
                cleanup(received.job_id,settings)
                if wait:
                    try:
                        payload=TasteSignal.model_validate_json(json.dumps(existing['value']['taste_signal'])).model_dump(mode='json')
                    except (KeyError, TypeError, ValueError, ValidationError):
                        raise ReelError('EXISTING_EDITED','Cette inspiration a été modifiée. Corrigez-la ou supprimez-la avant de réimporter.',409) from None
                else:
                    with db.connect() as c:
                        previous=c.execute('SELECT id FROM v2_reel_jobs WHERE owner_id=? AND couple_id=? AND fingerprint=? ORDER BY created_at DESC LIMIT 1',(member['id'],member['couple_id'],received.fingerprint)).fetchone()
                    job_id=previous['id'] if previous else None
                    payload={'job_id':job_id,'status':'completed','fact_id':existing['id'],'duplicate':True,'status_url':'/api/v2/reels/jobs/'+job_id if job_id else None}
                return JSONResponse(payload,headers={'Cache-Control':'no-store','X-Reel-Duplicate':'true'})
        except BaseException:
            cleanup(received.job_id,settings)
            raise
        LOGGER.info('reel_received kind=file backend=%s',backend)
        if wait:
            signal=await run_in_threadpool(process,received,member,config)
            return JSONResponse(signal.model_dump(mode='json'),headers={'Cache-Control':'no-store','X-Reel-Job-Id':received.job_id})
        tasks.add_task(background,received,member,config)
        return JSONResponse({'job_id':received.job_id,'status':'queued','status_url':'/api/v2/reels/jobs/'+received.job_id},status_code=202,headers={'Cache-Control':'no-store'})

    app.include_router(router)
    return service
