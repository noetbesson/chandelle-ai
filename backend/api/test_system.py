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
