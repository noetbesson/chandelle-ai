from datetime import datetime

from backend.streams.B_memory import CoupleProfile, PersonPreferences
from backend.streams.E_orchestrator.models import CandidateActivity, PlanRequest, TimeWindow
from backend.streams.E_orchestrator.planner import generate
from backend.streams.E_orchestrator.adapters import couple_profile_from_b

from . import DiscoveryConstraints, DiscoveryService, LocalActivityRepository


def window(start="2026-09-25T19:00:00", end="2026-09-25T23:15:00"):
    return TimeWindow(start=datetime.fromisoformat(start), end=datetime.fromisoformat(end))


def test_real_b_profile_changes_order_and_excludes_dislikes():
    discovery = DiscoveryService(LocalActivityRepository())
    plain = discovery.discover(CoupleProfile(couple_id="c"), window())
    cinema = discovery.discover(CoupleProfile(
        couple_id="c", shared_interests=["cinema"],
        user_a=PersonPreferences(interests=["cinema"]),
        user_b=PersonPreferences(interests=["cinema"])), window())
    assert plain[0].id == "saint_germain_jazz"
    assert cinema[0].id == "rive_gauche_cinema"
    assert cinema[0].user_a_score > next(item.user_a_score for item in plain
                                           if item.id == "rive_gauche_cinema")
    assert all(isinstance(item, CandidateActivity) for item in cinema)
    avoid = discovery.discover(CoupleProfile(couple_id="c", dislikes=["jazz"]), window())
    assert "saint_germain_jazz" not in {item.id for item in avoid}


def test_time_budget_types_tags_and_weekdays():
    discovery = DiscoveryService(LocalActivityRepository())
    profile = CoupleProfile(couple_id="c", typical_budget=30)
    evening = discovery.discover(profile, window(), DiscoveryConstraints(
        include_types=["restaurant"], required_tags=["casual"], limit=1))
    assert evening == []  # The qualifying dinner costs 48 euros for two.
    evening = discovery.discover(profile, window(), DiscoveryConstraints(
        include_types=["walk"], excluded_tags=["seine"]))
    assert evening == []  # The canal walk ends before the available window.
    assert "batignolles_market" not in {item.id for item in discovery.discover(
        CoupleProfile(couple_id="c"), window("2026-09-25T09:00:00", "2026-09-25T12:00:00"))}
    saturday = discovery.discover(CoupleProfile(couple_id="c"),
                                  window("2026-09-26T09:00:00", "2026-09-26T12:00:00"))
    assert [item.id for item in saturday] == ["batignolles_market"]


def test_positive_tag_filter_person_dislike_and_novelty():
    discovery = DiscoveryService(LocalActivityRepository())
    jazz_only = discovery.discover(CoupleProfile(couple_id="c"), window(),
                                   DiscoveryConstraints(include_types=["live_music"],
                                                        required_tags=["jazz"]))
    assert [item.id for item in jazz_only] == ["saint_germain_jazz"]
    no_jazz = discovery.discover(CoupleProfile(
        couple_id="c", user_b=PersonPreferences(dislikes=["jazz"])), window())
    assert "saint_germain_jazz" not in {item.id for item in no_jazz}
    seen = discovery.discover(CoupleProfile(couple_id="c", desired_novelty=1,
                                            recent_dates=["Saint-Germain jazz set"]), window())
    assert next(item.match_score for item in seen if item.id == "saint_germain_jazz") < jazz_only[0].match_score


def test_profile_budget_novelty_and_e_handoff():
    discovery = DiscoveryService(LocalActivityRepository())
    profile = CoupleProfile(couple_id="c", typical_budget=100,
                            shared_interests=["jazz"], recent_dates=["Saint-Germain jazz set"],
                            desired_novelty=1.0)
    candidates = discovery.discover(profile, window(), DiscoveryConstraints(max_total_budget=60))
    assert candidates
    assert all(item.price_per_person * 2 <= 60 for item in candidates)
    assert "saint_germain_jazz" in {item.id for item in candidates}
    e_profile = couple_profile_from_b(profile.model_dump(mode="json"))
    plans, _ = generate(PlanRequest(time_window=window(), couple_profile=e_profile,
                                    candidate_activities=candidates, constraints="under 60"))
    assert 1 <= len(plans) <= 3
    assert all(plan.estimated_total_eur <= 60 for plan in plans)
