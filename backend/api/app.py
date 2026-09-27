"""Single local HTTP application, authenticated web discovery and memory."""

from pathlib import Path
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.streams.E_orchestrator.legacy import ActivityReplacement, DatePipeline, PlanningFailure, RunRecord
from backend.streams.B_memory import CoupleProfile, MemoryService, SQLiteMemoryRepository
from backend.streams.C_discovery import DiscoveryService, LocalActivityRepository
from backend.streams.H_conversation import ConversationService, DateRequest, FeedbackRequest
from backend.streams.G_proactive import OpportunityDecision, ProactiveCheck, ProactiveService
from backend.streams.E_orchestrator.legacy import PlanResult


def create_app(db_path: str | Path | None = None) -> FastAPI:
    memory = MemoryService(SQLiteMemoryRepository(db_path) if db_path is not None
                           else SQLiteMemoryRepository())
    service = ConversationService(DatePipeline(memory, DiscoveryService(LocalActivityRepository())))
    app = FastAPI(title="Chandelle", version="0.1.0")

    @app.middleware('http')
    async def fresh_frontend(request, call_next):
        # Branch switches must not leave the browser running an older UI.
        path = request.url.path
        frontend = path in ('/', '/app', '/installer', '/partager', '/sw.js') or (
            path.startswith('/v2-static/') and Path(path).suffix in ('.html', '.mjs', '.js', '.css')
        )
        if frontend:
            request.scope['headers'] = [
                (key, value) for key, value in request.scope['headers']
                if key.lower() not in (b'if-none-match', b'if-modified-since')
            ]
        response = await call_next(request)
        if frontend:
            response.headers['Cache-Control'] = 'no-store'
        return response

    app.state.conversation = service
    static_dir = Path(__file__).with_name("static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def demo_page() -> FileResponse:
        return FileResponse(Path(__file__).resolve().parents[2] / "frontend" / "app" / "index.html")

    @app.get("/v1/demo", include_in_schema=False)
    def legacy_demo_page() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/date/request", response_model=PlanResult)
    def request_date(request: DateRequest) -> PlanResult:
        raise HTTPException(410,"Utilisez la recherche authentifiée /api/v2/dates/search.")

    @app.post("/v1/date/feedback", response_model=CoupleProfile)
    def feedback(request: FeedbackRequest) -> CoupleProfile:
        return service.submit_feedback(request)

    @app.post("/v1/date/replace", response_model=PlanResult)
    def replace_activity(request: ActivityReplacement) -> PlanResult:
        try:
            return service.pipeline.replace_activity(request)
        except PlanningFailure as exc:
            raise HTTPException(status_code=422, detail={"run_id": exc.run_id, "error": str(exc)}) from exc

    @app.get("/v1/couples/{couple_id}/memory", response_model=CoupleProfile)
    def memory_snapshot(couple_id: str) -> CoupleProfile:
        return service.memory_snapshot(couple_id)

    @app.get("/v1/runs/{run_id}", response_model=RunRecord)
    def run_status(run_id: str) -> RunRecord:
        record = service.pipeline.get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Unknown run")
        return record

    @app.post("/v1/proactive/check", response_model=OpportunityDecision)
    def proactive_check(request: ProactiveCheck) -> OpportunityDecision:
        raise HTTPException(410,"Utilisez la recherche authentifiée /api/v2/dates/search.")

    from backend.api.routes import install_routes
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    from starlette.exceptions import HTTPException as StarletteHTTPException
    v2_path = Path(db_path) if db_path is not None else Path(__file__).resolve().parents[2] / '.runtime' / 'chandelle_v2.sqlite3'
    install_routes(app, v2_path)
    if db_path is None:
        # Import the portable release once per digest into the same application database.
        # Explicit temporary databases in tests/tools remain empty unless imported explicitly.
        from backend.streams.C_discovery.local_catalog import ImportedCatalog, BUNDLE
        if BUNDLE.is_file():
            ImportedCatalog(app.state.v2['db']).import_bundle()
    from backend.api.pwa import install_pwa
    install_pwa(app)
    v2_static = Path(__file__).resolve().parents[2] / 'frontend' / 'app'
    app.mount('/v2-static', StaticFiles(directory=v2_static), name='v2-static')

    @app.get('/app', include_in_schema=False)
    def v2_page():
        return FileResponse(v2_static / 'index.html')

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        if request.url.path.startswith('/api/v2'):
            return JSONResponse(status_code=422, content={'error': {'code': 'validation_error', 'message': 'Invalid request fields'}})
        return JSONResponse(status_code=422, content={'detail': str(exc)})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        if request.url.path.startswith('/api/v2'):
            return JSONResponse(status_code=exc.status_code, content={'error': {'code': str(exc.status_code), 'message': exc.detail}})
        return JSONResponse(status_code=exc.status_code, content={'detail': exc.detail})

    async def domain_error(request, exc):
        status = 403 if isinstance(exc, PermissionError) else 404 if isinstance(exc, KeyError) else 422
        return JSONResponse(status_code=status, content={'error': {'code': getattr(exc,'code',str(status)), 'message': str(exc)}})
    for error in (ValueError, PermissionError, KeyError):
        app.add_exception_handler(error, domain_error)
    return app


app = create_app(os.getenv('CHANDELLE_DB_PATH'))
