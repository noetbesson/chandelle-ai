import json
import sqlite3

import pytest

from backend.streams.C_discovery.v2 import CatalogService
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
