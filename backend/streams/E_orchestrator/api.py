"""Stream E FastAPI routes and in-process run supervision."""

from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .models import PlanRequest, PlansResponse, ReplaceRequest
from .planner import NoFeasiblePlan, generate, replace
from .repository import load_candidates


class RunStatus(BaseModel):
    run_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    plan_count: int = 0
    error: str | None = None


app = FastAPI(title="Chandelle Stream E Date Orchestrator", version="0.1.0")
_runs: dict[str, RunStatus] = {}
_lock = Lock()


def _save(run: RunStatus) -> None:
    with _lock:
        _runs[run.run_id] = run


def _execute(request: PlanRequest | ReplaceRequest, replacement: bool) -> PlansResponse:
    run = RunStatus(run_id=uuid4().hex, status="running", started_at=datetime.now(timezone.utc))
    _save(run)
    try:
        if request.candidate_activities is None:
            request = request.model_copy(update={"candidate_activities": load_candidates()})
        plans, rejected = replace(request) if replacement else generate(request)
    except (ValueError, OSError) as exc:
        run.status = "failed"
        run.error = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        _save(run)
        raise HTTPException(status_code=422 if isinstance(exc, (ValueError, NoFeasiblePlan)) else 500,
                            detail={"run_id": run.run_id, "error": str(exc)}) from exc
    run.status = "completed"
    run.plan_count = len(plans)
    run.finished_at = datetime.now(timezone.utc)
    _save(run)
    return PlansResponse(run_id=run.run_id, status=run.status, plans=plans, rejected=rejected)


@app.post("/plans", response_model=PlansResponse)
def create_plans(request: PlanRequest) -> PlansResponse:
    return _execute(request, False)


@app.post("/plans/replace", response_model=PlansResponse)
def replace_activity(request: ReplaceRequest) -> PlansResponse:
    return _execute(request, True)


@app.get("/runs/{run_id}", response_model=RunStatus)
def get_run(run_id: str) -> RunStatus:
    with _lock:
        run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Unknown run")
    return run


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
