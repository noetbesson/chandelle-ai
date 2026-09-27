"""V1 activity source retired; preserve legacy memory and explicit migration errors."""
import json
import subprocess
import sys

from fastapi.testclient import TestClient
from backend.api.app import create_app
from backend.streams.B_memory import MemoryService,ProfileUpdate,SQLiteMemoryRepository
from backend.streams.C_discovery import LocalActivityRepository
import pytest

@pytest.mark.parametrize('route', ['/v1/date/request','/v1/proactive/check'])
def test_retired_search_redirects_to_authenticated_pipeline(tmp_path,route):
    client=TestClient(create_app(tmp_path/'legacy.sqlite3'))
    response=client.post(route,json={'couple_id':'test','text':'Une sortie','time_window':{'start':'2026-09-25T19:00:00','end':'2026-09-25T23:15:00'}})
    assert response.status_code==410 and '/api/v2/dates/search' in response.text
    assert client.get('/health').status_code==200

def test_no_legacy_default_activity_source():assert LocalActivityRepository().list_activities()==[]

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
