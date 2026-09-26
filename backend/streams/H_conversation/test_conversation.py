from datetime import datetime

from backend.api.pipeline import DatePipeline
from backend.streams.B_memory import MemoryService, ProfileUpdate, SQLiteMemoryRepository
from backend.streams.C_discovery import DiscoveryService, LocalActivityRepository
from backend.streams.H_conversation import ConversationService, DateRequest, FeedbackRequest
from backend.streams.E_orchestrator.models import TimeWindow


def test_request_feedback_and_reopen(tmp_path):
    path = tmp_path / "memory.sqlite3"
    service = ConversationService(DatePipeline(
        MemoryService(SQLiteMemoryRepository(path)), DiscoveryService(LocalActivityRepository())))
    result = service.request_date(DateRequest(
        couple_id="couple-1", text="We want jazz under €80",
        time_window=TimeWindow(start=datetime(2026, 9, 25, 19), end=datetime(2026, 9, 25, 23, 15)),
        profile_update=ProfileUpdate(shared_interests=["jazz"], typical_budget=100)))
    assert result.plans and all(p.estimated_total_eur <= 80 for p in result.plans)
    assert all(any("jazz" in a.id for a in p.activities) for p in result.plans)
    snapshot = service.submit_feedback(FeedbackRequest(
        couple_id="couple-1", date_plan_id=result.plans[0].date_plan_id,
        rating=5, sentiment="positive", liked_tags=["music"],
        disliked_tags=["crowds"], decision="selected",
        occurred_at=datetime(2026, 9, 25, 21), activities=["Saint-Germain jazz set"]))
    assert snapshot.feedback[-1].rating == 5
    reopened = MemoryService(SQLiteMemoryRepository(path)).get_snapshot("couple-1")
    assert reopened.shared_interests == ["jazz", "music"]
    assert reopened.dislikes == ["crowds"]
    assert reopened.selections[-1].decision == "selected"
    assert reopened.date_history[-1].activities == ["Saint-Germain jazz set"]
