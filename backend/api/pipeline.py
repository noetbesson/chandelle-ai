"""The provisional B → C → E composition boundary."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.streams.B_memory import MemoryService, ProfileUpdate
from backend.streams.C_discovery import DiscoveryConstraints, DiscoveryService
from backend.streams.E_orchestrator.adapters import couple_profile_from_b
from backend.streams.E_orchestrator.models import DatePlan, PlanRequest, ReplaceRequest, TimeWindow
from backend.streams.E_orchestrator.planner import generate, replace


class CoreRequest(BaseModel):
    couple_id: str = Field(min_length=1)
    time_window: TimeWindow
    profile_update: ProfileUpdate | None = None
    discovery: DiscoveryConstraints = Field(default_factory=DiscoveryConstraints)
    max_plans: int = Field(default=3, ge=1, le=3)


class TraceStep(BaseModel):
    stream: str
    detail: str


class PlanResult(BaseModel):
    run_id: str
    status: str = "completed"
    plans: list[DatePlan]
    trace: list[TraceStep]
    rejected: dict[str, str] = Field(default_factory=dict)
    external_systems: str = "mocked/local"
    booking_requires_human_confirmation: bool = True
    availability: TimeWindow | None = None
    budget_cap: float | None = None


class ActivityReplacement(BaseModel):
    couple_id: str = Field(min_length=1)
    time_window: TimeWindow
    plan: DatePlan
    replace_activity_id: str = Field(min_length=1)
    budget_cap: float | None = Field(default=None, ge=0)


class RunRecord(BaseModel):
    run_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None
    trace: list[TraceStep] = Field(default_factory=list)
    plan_count: int = 0


class PlanningFailure(ValueError):
    def __init__(self, run_id: str, reason: str):
        super().__init__(reason)
        self.run_id = run_id


class DatePipeline:
    def __init__(self, memory: MemoryService, discovery: DiscoveryService):
        self.memory = memory
        self.discovery = discovery
        self.runs: dict[str, RunRecord] = {}

    def plan(self, request: CoreRequest) -> PlanResult:
        run_id = uuid4().hex
        run = RunRecord(run_id=run_id, status="running", started_at=datetime.now(timezone.utc))
        self.runs[run_id] = run
        try:
            profile = (self.memory.update_profile(request.couple_id, request.profile_update)
                       if request.profile_update else self.memory.get_snapshot(request.couple_id))
            run.trace.append(TraceStep(stream="B", detail=f"Loaded persistent profile for {profile.couple_id}"))
            candidates = self.discovery.discover(profile, request.time_window, request.discovery)
            run.trace.append(TraceStep(stream="C", detail=f"Discovered {len(candidates)} local candidates"))
            e_profile = couple_profile_from_b(profile.model_dump(mode="json"))
            # C's budget check applies per candidate. E must cap the whole date.
            if request.discovery.max_total_budget is not None:
                cap = request.discovery.max_total_budget
                e_profile.typical_budget = min(e_profile.typical_budget, cap) if e_profile.typical_budget is not None else cap
            plans, rejected = generate(PlanRequest(
                time_window=request.time_window, couple_profile=e_profile,
                candidate_activities=candidates, max_plans=request.max_plans))
            run.trace.append(TraceStep(stream="E", detail=f"Composed {len(plans)} date plans"))
            run.status = "completed"
            run.plan_count = len(plans)
            return PlanResult(run_id=run_id, plans=plans, trace=run.trace, rejected=rejected,
                              availability=request.time_window, budget_cap=e_profile.typical_budget)
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            raise PlanningFailure(run_id, str(exc)) from exc
        finally:
            run.finished_at = datetime.now(timezone.utc)

    def get_run(self, run_id: str) -> RunRecord | None:
        return self.runs.get(run_id)

    def replace_activity(self, request: ActivityReplacement) -> PlanResult:
        run_id = uuid4().hex
        run = RunRecord(run_id=run_id, status="running", started_at=datetime.now(timezone.utc))
        self.runs[run_id] = run
        try:
            profile = self.memory.get_snapshot(request.couple_id)
            run.trace.append(TraceStep(stream="B", detail=f"Loaded persistent profile for {profile.couple_id}"))
            rules = DiscoveryConstraints(max_total_budget=request.budget_cap)
            candidates = self.discovery.discover(profile, request.time_window, rules)
            run.trace.append(TraceStep(stream="C", detail=f"Discovered {len(candidates)} local candidates"))
            e_profile = couple_profile_from_b(profile.model_dump(mode="json"))
            if request.budget_cap is not None:
                e_profile.typical_budget = min(e_profile.typical_budget, request.budget_cap) if e_profile.typical_budget is not None else request.budget_cap
            plans, rejected = replace(ReplaceRequest(
                time_window=request.time_window, couple_profile=e_profile,
                candidate_activities=candidates, plan=request.plan,
                replace_activity_id=request.replace_activity_id, max_plans=3))
            run.trace.append(TraceStep(stream="E", detail=f"Composed {len(plans)} replacements"))
            run.status = "completed"
            run.plan_count = len(plans)
            return PlanResult(run_id=run_id, plans=plans, trace=run.trace, rejected=rejected,
                              availability=request.time_window, budget_cap=e_profile.typical_budget)
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            raise PlanningFailure(run_id, str(exc)) from exc
        finally:
            run.finished_at = datetime.now(timezone.utc)
