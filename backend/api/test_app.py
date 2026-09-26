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
