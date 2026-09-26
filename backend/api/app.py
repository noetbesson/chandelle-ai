"""Local HTTP composition for the offline demo."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.pipeline import ActivityReplacement, DatePipeline, PlanningFailure, RunRecord
from backend.streams.B_memory import CoupleProfile, MemoryService, SQLiteMemoryRepository
from backend.streams.C_discovery import DiscoveryService, LocalActivityRepository
from backend.streams.H_conversation import ConversationService, DateRequest, FeedbackRequest
from backend.streams.G_proactive import OpportunityDecision, ProactiveCheck, ProactiveService
from backend.api.pipeline import PlanResult


def create_app(db_path: str | Path | None = None) -> FastAPI:
    memory = MemoryService(SQLiteMemoryRepository(db_path) if db_path is not None
                           else SQLiteMemoryRepository())
    service = ConversationService(DatePipeline(memory, DiscoveryService(LocalActivityRepository())))
    proactive = ProactiveService(service.pipeline)
    app = FastAPI(title="Chandelle Offline Demo", version="0.1.0")
    app.state.conversation = service
    static_dir = Path(__file__).with_name("static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def demo_page() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/date/request", response_model=PlanResult)
    def request_date(request: DateRequest) -> PlanResult:
        try:
            return service.request_date(request)
        except PlanningFailure as exc:
            raise HTTPException(status_code=422, detail={"run_id": exc.run_id, "error": str(exc)}) from exc

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
        try:
            return proactive.check(request)
        except PlanningFailure as exc:
            raise HTTPException(status_code=422, detail={"run_id": exc.run_id, "error": str(exc)}) from exc

    return app


app = create_app()
