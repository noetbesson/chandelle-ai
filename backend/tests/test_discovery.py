import json
import sqlite3

import pytest

from backend.streams.C_discovery.service import CatalogService
from backend.streams.E_orchestrator.models import CandidateActivity


class Database:
    def __init__(self, path):
        self.path = path
        with self.connect() as con:
            con.executescript('''
            CREATE TABLE v2_activities(id TEXT PRIMARY KEY,payload TEXT);
            CREATE TABLE v2_activity_states(user_id TEXT,activity_id TEXT,state TEXT,updated_at TEXT,PRIMARY KEY(user_id,activity_id));
            CREATE TABLE v2_memberships(couple_id TEXT,user_id TEXT,role TEXT);
            CREATE TABLE v2_plans(couple_id TEXT,status TEXT,payload TEXT);
            INSERT INTO v2_memberships VALUES ('c','a','A'),('c','b','B');
            ''')
    def connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con


class Memory:
    def __init__(self):
        self.context = {'person_a': {}, 'person_b': {}, 'couple': {}}
        self.calls = []
    def planning_context(self, couple_id):
        self.calls.append(couple_id)
        return self.context


@pytest.fixture
def service(tmp_path):
    service = CatalogService(Database(tmp_path/'catalog.db'), Memory())
    service.seed()
    return service


def discover(service, **kwargs):
    return service.discover('c', {'start': '2026-09-26T18:00:00', 'end': '2026-09-26T23:00:00'}, **kwargs)


def test_persistent_seed_browse_and_candidate_contract(service):
    service.seed()
    assert service.browse(limit=100)['total'] == 40
    assert service.browse(query='clay')['total'] == 4
    assert service.browse(category='food')['total'] == 4
    reopened = CatalogService(service.db, service.memory)
    assert reopened.get('demo_food_1')['demo'] is True
    assert reopened.get('demo_food_1')['last_verified_at'] is None
    results = discover(service)
    assert len(results) == 20
    for row in results:
        CandidateActivity.model_validate(row['candidate'])
    assert service.memory.calls == ['c']


def test_hard_filters_person_b_dislike_budget_time_accessibility(service):
    service.memory.context['person_b'] = {'dislikes': ['food'], 'constraints': {'accessibility': ['wheelchair']}}
    rows = discover(service, budget=30)
    assert rows
    assert all(row['activity']['category'] not in {'food','sport','travel'} for row in rows)
    assert all(row['activity']['price_per_person']*2 <= 30 for row in rows)
    assert all(row['activity']['start'] in {'19:00','21:00'} for row in rows)
    assert discover(service, radius_km=0) == []
    service.memory.context['person_b']['constraints']['days'] = ['monday']
    assert discover(service) == []


def test_fairness_and_safe_evidence(service):
    service.memory.context['person_a'] = {'interests': ['food','culture']}
    service.memory.context['person_b'] = {'interests': ['culture'], 'private_text': 'NEVER OUTPUT THIS'}
    rows = discover(service)
    culture = next(row for row in rows if row['activity']['category'] == 'culture')
    food = next(row for row in rows if row['activity']['category'] == 'food')
    assert culture['couple_score'] > food['couple_score']
    a,b = food['person_a_score'],food['person_b_score']
    assert food['components']['fairness'] == pytest.approx(.6*min(a,b)+.4*(a+b)/2)
    assert 'NEVER OUTPUT THIS' not in json.dumps(rows)


def test_state_isolation_rejection_and_history_novelty(service):
    initial = {row['activity']['id']: row for row in discover(service)}
    service.set_state('a','demo_food_3','saved')
    changed = {row['activity']['id']: row for row in discover(service)}
    assert changed['demo_food_3']['person_a_score'] > initial['demo_food_3']['person_a_score']
    assert changed['demo_food_3']['person_b_score'] == initial['demo_food_3']['person_b_score']
    service.set_state('b','demo_food_3','disliked')
    assert 'demo_food_3' not in {row['activity']['id'] for row in discover(service)}
    service.set_state('outsider','demo_culture_3','disliked')
    assert 'demo_culture_3' in {row['activity']['id'] for row in discover(service)}
    with service.db.connect() as con:
        con.execute('INSERT INTO v2_plans VALUES (?,?,?)', ('c','completed',json.dumps({'activities':[{'id':'demo_culture_3'}]})))
    changed = {row['activity']['id']: row for row in discover(service)}
    assert changed['demo_culture_3']['components']['novelty_penalty'] > 0


def test_budget_dietary_travel_diversity_and_errors(service):
    service.memory.context['person_a'] = {'budget': {'max': 10, 'unit': 'person'}, 'constraints': {'dietary': ['vegan']}}
    rows = discover(service)
    assert all(row['activity']['price_per_person'] <= 10 for row in rows)
    assert any(row['components']['diversity_penalty'] > 0 for row in rows)
    service.memory.context['person_a']['constraints']['travel_minutes'] = 0
    assert discover(service) == []
    with pytest.raises(ValueError):
        service.set_state('a','demo_food_1','invalid')
    with pytest.raises(KeyError):
        service.get('unknown')
    with pytest.raises(ValueError):
        service.browse(limit=101)


from datetime import datetime

from backend.streams.B_memory import CoupleProfile, PersonPreferences
from backend.streams.E_orchestrator.models import CandidateActivity, PlanRequest, TimeWindow
from backend.streams.E_orchestrator.planner import generate
from backend.streams.E_orchestrator.adapters import couple_profile_from_b

from backend.streams.C_discovery import DiscoveryConstraints, DiscoveryService, LocalActivityRepository


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
