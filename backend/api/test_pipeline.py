from datetime import datetime

from backend.api.pipeline import CoreRequest, DatePipeline
from backend.streams.B_memory import MemoryService, ProfileUpdate, SQLiteMemoryRepository
from backend.streams.C_discovery import DiscoveryConstraints, DiscoveryService, LocalActivityRepository
from backend.streams.E_orchestrator.models import TimeWindow


def test_core_pipeline_uses_b_c_e_and_caps_full_plan(tmp_path):
    pipeline = DatePipeline(MemoryService(SQLiteMemoryRepository(tmp_path / "memory.sqlite3")),
                            DiscoveryService(LocalActivityRepository()))
    result = pipeline.plan(CoreRequest(
        couple_id="test-couple",
        time_window=TimeWindow(start=datetime(2026, 9, 25, 19), end=datetime(2026, 9, 25, 23, 15)),
        profile_update=ProfileUpdate(shared_interests=["jazz"], typical_budget=100),
        discovery=DiscoveryConstraints(max_total_budget=60),
    ))
    assert 1 <= len(result.plans) <= 3
    assert [step.stream for step in result.trace] == ["B", "C", "E"]
    assert all(plan.estimated_total_eur <= 60 for plan in result.plans)
    assert pipeline.memory.get_snapshot("test-couple").shared_interests == ["jazz"]
    assert pipeline.get_run(result.run_id).status == "completed"
