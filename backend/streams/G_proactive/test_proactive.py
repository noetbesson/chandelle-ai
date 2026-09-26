from datetime import datetime, timedelta, timezone

from backend.api.pipeline import DatePipeline
from backend.streams.B_memory import DateHistoryEntry, MemoryService, SQLiteMemoryRepository
from backend.streams.C_discovery import DiscoveryService, LocalActivityRepository
from backend.streams.E_orchestrator.models import TimeWindow
from backend.streams.G_proactive import ProactiveCheck, ProactiveService


def test_proactive_trigger_uses_same_pipeline(tmp_path):
    pipeline = DatePipeline(MemoryService(SQLiteMemoryRepository(tmp_path / "memory.sqlite3")),
                            DiscoveryService(LocalActivityRepository()))
    proactive = ProactiveService(pipeline)
    window = TimeWindow(start=datetime(2026, 9, 25, 19), end=datetime(2026, 9, 25, 23, 15))
    now = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)
    decision = proactive.check(ProactiveCheck(couple_id="c", time_window=window), now=now)
    assert decision.triggered and decision.result
    assert [step.stream for step in decision.result.trace] == ["B", "C", "E"]
    assert len(decision.result.plans) == 1
    assert decision.candidate_count > 0
    pipeline.memory.record_date("c", DateHistoryEntry(
        date_plan_id="recent", occurred_at=now - timedelta(days=2), activities=["Jazz club"]))
    recent = proactive.check(ProactiveCheck(couple_id="c", time_window=window), now=now)
    assert not recent.triggered and recent.days_since_previous_date == 2
    assert "threshold" in recent.reason


def test_proactive_no_candidates(tmp_path):
    pipeline = DatePipeline(MemoryService(SQLiteMemoryRepository(tmp_path / "memory.sqlite3")),
                            DiscoveryService(LocalActivityRepository()))
    decision = ProactiveService(pipeline).check(ProactiveCheck(
        couple_id="c", time_window=TimeWindow(
            start=datetime(2026, 9, 25, 1), end=datetime(2026, 9, 25, 2))))
    assert not decision.triggered and decision.candidate_count == 0
