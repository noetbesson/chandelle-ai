from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.streams.E_orchestrator.adapters import couple_profile_from_b
from backend.streams.E_orchestrator.api import app
from backend.streams.E_orchestrator.models import PlanRequest, ReplaceRequest, TimeWindow
from backend.streams.E_orchestrator.planner import NoFeasiblePlan, generate, replace


def item(id, start, end, price=10, score=0.8, kind="activity", lat=48.85, a=None, b=None):
    return {"id": id, "type": kind, "name": id, "start": start, "end": end,
            "price_per_person": price, "location": {"lat": lat, "lng": 2.34},
            "match_score": score, "user_a_score": a, "user_b_score": b}


def request(activities, budget=100, **kwargs):
    return PlanRequest.model_validate({
        "time_window": {"start": "2026-09-25T19:30", "end": "2026-09-25T23:45", "duration_minutes": 255},
        "couple_profile": {"shared_interests": ["jazz"], "dislikes": ["formal"], "typical_budget": budget},
        "candidate_activities": activities, **kwargs})


def test_time_window_validation():
    with pytest.raises(ValidationError):
        TimeWindow(start=datetime(2026, 9, 25, 20), end=datetime(2026, 9, 25, 21), duration_minutes=30)


def test_activity_validation_and_duplicate_ids():
    with pytest.raises(ValidationError):
        request([item("bad", "20:00", "21:00", score=1.2)])
    with pytest.raises(ValueError, match="Duplicate activity id"):
        generate(request([item("same", "20:00", "21:00"), item("same", "21:15", "22:00")]))


def test_overnight_window():
    req = PlanRequest.model_validate({
        "time_window": {"start": "2026-09-25T22:00", "end": "2026-09-26T01:00", "duration_minutes": 180},
        "couple_profile": {"typical_budget": 100},
        "candidate_activities": [item("late", "00:10", "00:50")]})
    plans, _ = generate(req)
    assert plans[0].start.isoformat() == "2026-09-26T00:10:00"


def test_filter_budget_window_and_dislike():
    req = request([item("good", "20:00", "21:00"), item("early", "18:00", "19:00"),
                   item("expensive", "21:00", "22:00", 60),
                   item("formal", "21:00", "22:00")])
    plans, rejected = generate(req)
    assert len(plans) == 1
    assert [a.id for a in plans[0].activities] == ["good"]
    assert rejected == {"early": "outside available window", "expensive": "over couple budget", "formal": "couple dislike"}


def test_coherent_schedule_and_total_budget():
    req = request([item("dinner", "20:00", "21:00", 35, kind="restaurant"),
                   item("music", "21:15", "22:30", 15, kind="music"),
                   item("overlap", "20:30", "21:45", 5),
                   item("far", "21:15", "22:30", 5, lat=48.95)], budget=100)
    plans, _ = generate(req)
    multi = next(plan for plan in plans if [a.id for a in plan.activities] == ["dinner", "music"])
    assert multi.estimated_total_eur == 100
    assert all(not {"dinner", "overlap"}.issubset({a.id for a in plan.activities}) for plan in plans)
    assert all(not {"dinner", "far"}.issubset({a.id for a in plan.activities}) for plan in plans)


def test_fairness_ranks_balanced_option():
    req = request([item("one_sided", "20:00", "21:00", score=0.95, a=1, b=0),
                   item("balanced", "20:00", "21:00", score=0.75, a=0.75, b=0.75)], max_plans=2)
    plans, _ = generate(req)
    assert plans[0].activities[0].id == "balanced"


def test_replacement_preserves_kept_activity():
    activities = [item("dinner", "20:00", "21:00", kind="restaurant"),
                  item("music", "21:15", "22:30", kind="music"),
                  item("comedy", "21:20", "22:20", kind="comedy")]
    req = request(activities)
    original = next(p for p in generate(req)[0] if [a.id for a in p.activities] == ["dinner", "music"])
    replacement = ReplaceRequest.model_validate({**req.model_dump(), "plan": original.model_dump(),
                                                  "replace_activity_id": "music"})
    plans, _ = replace(replacement)
    assert [a.id for a in plans[0].activities] == ["dinner", "comedy"]
    assert plans[0].activities[0] == original.activities[0]


def test_replacement_rejects_changed_kept_activity():
    activities = [item("dinner", "20:00", "21:00"), item("music", "21:15", "22:30"),
                  item("comedy", "21:20", "22:20")]
    req = request(activities)
    original = next(p for p in generate(req)[0] if [a.id for a in p.activities] == ["dinner", "music"])
    changed = [dict(a) for a in activities]
    changed[0]["price_per_person"] = 20
    replacement = ReplaceRequest.model_validate({**request(changed).model_dump(), "plan": original.model_dump(),
                                                  "replace_activity_id": "music"})
    with pytest.raises(ValueError, match="Kept activity unavailable or changed"):
        replace(replacement)


def test_replacement_keeps_low_scored_required_activity():
    activities = [item("kept", "20:00", "21:00", score=0.01),
                  item("old", "21:20", "22:20", score=0.8),
                  item("new", "21:25", "22:25", score=0.9)]
    activities += [item(f"other_{i}", "20:00", "21:00", score=0.5) for i in range(60)]
    original_req = request(activities[:3], max_plans=3)
    original = next(p for p in generate(original_req)[0] if [a.id for a in p.activities] == ["kept", "new"])
    req = request(activities)
    replacement = ReplaceRequest.model_validate({**req.model_dump(), "plan": original.model_dump(),
                                                  "replace_activity_id": "new"})
    plans, _ = replace(replacement)
    assert [a.id for a in plans[0].activities] == ["kept", "old"]


def test_constraints_and_infeasible():
    req = request([item("music", "21:00", "22:00")], constraints="after 21:30")
    with pytest.raises(NoFeasiblePlan):
        generate(req)
    with pytest.raises(ValueError, match="Unsupported constraint"):
        generate(request([item("music", "21:00", "22:00")], constraints="surprise me"))
    plans, rejected = generate(request([item("music", "21:00", "22:00"), item("comedy", "20:00", "20:45")],
                                       constraints="no comedy, under €30"))
    assert plans[0].activities[0].id == "music"
    assert rejected["comedy"] == "excluded by constraint"


def test_adapter_alternate_profile_fields():
    profile = couple_profile_from_b({"likes": ["jazz"], "budget_per_person_max": 70,
                                     "novelty_preference": 0.8})
    assert profile.typical_budget == 140
    assert profile.shared_interests == ["jazz"]


def test_api_local_repository_and_run_status():
    client = TestClient(app)
    payload = request([]).model_dump(mode="json")
    payload.pop("candidate_activities")
    response = client.post("/plans", json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert 1 <= len(result["plans"]) <= 3
    assert client.get(f"/runs/{result['run_id']}").json()["status"] == "completed"
    assert client.get("/runs/missing").status_code == 404


def test_api_failure_records_status():
    client = TestClient(app)
    response = client.post("/plans", json=request([]).model_dump(mode="json"))
    assert response.status_code == 422
    run_id = response.json()["detail"]["run_id"]
    assert client.get(f"/runs/{run_id}").json()["status"] == "failed"
