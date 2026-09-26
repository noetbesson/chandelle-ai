from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_h_api_request_feedback_and_memory(tmp_path):
    client = TestClient(create_app(tmp_path / "memory.sqlite3"))
    assert client.get("/health").json() == {"status": "ok"}
    response = client.post("/v1/date/request", json={
        "couple_id": "demo", "text": "A jazz date under €80",
        "time_window": {"start": "2026-09-25T19:00:00", "end": "2026-09-25T23:15:00"},
        "profile_update": {"shared_interests": ["jazz"]}})
    assert response.status_code == 200, response.text
    result = response.json()
    assert 1 <= len(result["plans"]) <= 3
    assert [step["stream"] for step in result["trace"]] == ["B", "C", "E"]
    assert client.get(f"/v1/runs/{result['run_id']}").json()["status"] == "completed"
    feedback = client.post("/v1/date/feedback", json={
        "couple_id": "demo", "date_plan_id": result["plans"][0]["date_plan_id"],
        "rating": 5, "sentiment": "positive", "liked_tags": ["jazz"]})
    assert feedback.status_code == 200
    assert client.get("/v1/couples/demo/memory").json()["feedback"][-1]["rating"] == 5


def test_h_api_error_run_status(tmp_path):
    client = TestClient(create_app(tmp_path / "memory.sqlite3"))
    response = client.post("/v1/date/request", json={
        "couple_id": "demo", "text": "A date", "categories": ["underwater palace"],
        "time_window": {"start": "2026-09-25T19:00:00", "end": "2026-09-25T23:15:00"}})
    assert response.status_code == 422
    run_id = response.json()["detail"]["run_id"]
    assert client.get(f"/v1/runs/{run_id}").json()["status"] == "failed"


def test_proactive_api_trigger(tmp_path):
    client = TestClient(create_app(tmp_path / "memory.sqlite3"))
    response = client.post("/v1/proactive/check", json={
        "couple_id": "demo", "time_window": {
            "start": "2026-09-25T19:00:00", "end": "2026-09-25T23:15:00"}})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["triggered"] and body["result"]["plans"]
    assert "matching activities" in body["reason"]


def test_replacement_preserves_other_activity_and_static_ui(tmp_path):
    client = TestClient(create_app(tmp_path / "memory.sqlite3"))
    request = client.post("/v1/date/request", json={
        "couple_id": "demo", "text": "A date",
        "time_window": {"start": "2026-09-25T19:00:00", "end": "2026-09-25T23:15:00"}})
    assert request.status_code == 200
    original = request.json()
    plan = next(plan for plan in original["plans"] if
                {"saint_germain_bistro", "rive_gauche_cinema"} ==
                {activity["id"] for activity in plan["activities"]})
    replacement = client.post("/v1/date/replace", json={
        "couple_id": "demo", "time_window": original["availability"],
        "plan": plan, "replace_activity_id": "rive_gauche_cinema"})
    assert replacement.status_code == 200, replacement.text
    assert all("saint_germain_bistro" in {activity["id"] for activity in item["activities"]}
               for item in replacement.json()["plans"])
    assert all("rive_gauche_cinema" not in {activity["id"] for activity in item["activities"]}
               for item in replacement.json()["plans"])
    page = client.get("/")
    assert page.status_code == 200 and "Chandelle" in page.text
    assert client.get("/static/styles.css").status_code == 200
    script = client.get("/static/app.js")
    assert script.status_code == 200
    for route in ("/v1/date/request", "/v1/date/replace", "/v1/date/feedback",
                  "/v1/couples/", "/v1/proactive/check"):
        assert route in script.text


from datetime import datetime

from backend.streams.E_orchestrator.legacy import CoreRequest, DatePipeline
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


"""System checks over the local API and independent Python processes."""

import json
import subprocess
import sys

from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_memory_survives_clean_process(tmp_path):
    db = str(tmp_path / "memory.sqlite3")
    writer = """
import sys
from backend.streams.B_memory import MemoryService, ProfileUpdate, SQLiteMemoryRepository
MemoryService(SQLiteMemoryRepository(sys.argv[1])).update_profile(
    'process-couple', ProfileUpdate(shared_interests=['cinema'], typical_budget=70))
"""
    reader = """
import json, sys
from backend.streams.B_memory import MemoryService, SQLiteMemoryRepository
profile = MemoryService(SQLiteMemoryRepository(sys.argv[1])).get_snapshot('process-couple')
print(profile.model_dump_json())
"""
    subprocess.run([sys.executable, "-c", writer, db], check=True, capture_output=True, text=True)
    result = subprocess.run([sys.executable, "-c", reader, db], check=True, capture_output=True, text=True)
    profile = json.loads(result.stdout)
    assert profile["shared_interests"] == ["cinema"]
    assert profile["typical_budget"] == 70


def test_end_to_end_uses_no_network(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("External network attempt")

    monkeypatch.setattr("socket.socket.connect", forbidden)
    client = TestClient(create_app(tmp_path / "memory.sqlite3"))
    request = client.post("/v1/date/request", json={
        "couple_id": "qa", "text": "jazz under €80",
        "time_window": {"start": "2026-09-25T19:00:00", "end": "2026-09-25T23:15:00"},
        "profile_update": {"shared_interests": ["jazz"]}})
    assert request.status_code == 200, request.text
    plan = request.json()["plans"][0]
    feedback = client.post("/v1/date/feedback", json={
        "couple_id": "qa", "date_plan_id": plan["date_plan_id"],
        "rating": 4, "liked_tags": ["music"]})
    assert feedback.status_code == 200
    assert client.get("/v1/couples/qa/memory").json()["feedback"][-1]["rating"] == 4
    proactive = client.post("/v1/proactive/check", json={
        "couple_id": "qa", "time_window": {
            "start": "2026-09-25T19:00:00", "end": "2026-09-25T23:15:00"}})
    assert proactive.status_code == 200
    assert proactive.json()["triggered"]


from datetime import datetime, timedelta, timezone

from backend.streams.E_orchestrator.legacy import DatePipeline
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


from datetime import datetime

from backend.streams.E_orchestrator.legacy import DatePipeline
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
