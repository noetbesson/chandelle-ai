"""Real SQLite/API flow, fake provider responses; never external network."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import json

import pytest

from backend.db import Database
from backend.integrations.ai_budget import AIBudget, BudgetDenied
from backend.integrations.openai import OpenAIAdapter
from backend.streams.C_discovery.web import WebDiscovery, WebQuery
from backend.tests.test_api import client, offline_only, ready, headers, PREFIX


class Response:
    usage = SimpleNamespace(model_dump=lambda: {'input_tokens': 500, 'output_tokens': 200})

    def model_dump(self):
        return {'status': 'completed', 'output': [
            {'type': 'web_search_call', 'status': 'completed'},
            {'type': 'message', 'content': [{'type': 'output_text', 'text': 'Exposition à Paris [source]',
                'annotations': [{'type': 'url_citation', 'url': 'https://www.paris.fr/evenements/example',
                                 'title': 'Agenda Paris', 'start_index': 19, 'end_index': 27}]}]}]}


class Client:
    def __init__(self, response=None):
        self.responses = self
        self.calls = []
        self.response = response or Response()

    def create(self, **kw):
        self.calls.append(kw)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def enable(monkeypatch):
    monkeypatch.setenv('OPENAI_ENABLED', '1')
    monkeypatch.setenv('OPENAI_WEB_ENABLED', '1')


def test_atomic_budget_survives_restart_and_concurrent_calls(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_TOTAL_RESERVE_USD', '.10')
    monkeypatch.setenv('OPENAI_DAILY_RESERVE_USD', '1')
    db = Database(tmp_path / 'budget.sqlite3')
    def run(_):
        try:return AIBudget(db).reserve('web', 'gpt-4.1-mini')
        except BudgetDenied:return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert len([r for r in pool.map(run, range(6)) if r]) == 1
    assert AIBudget(Database(db.path)).status()['total_reserved'] == .1


def test_unknown_model_zero_budget_and_failure_do_not_bypass_quota(tmp_path, monkeypatch):
    db = Database(tmp_path / 'budget.sqlite3')
    budget = AIBudget(db)
    with pytest.raises(BudgetDenied, match='model_not_budgeted'):
        budget.reserve('text', 'unknown-expensive-model')
    ticket = budget.reserve('text', 'gpt-4.1-mini')
    budget.finish(ticket, 'failed')
    assert budget.status()['total_reserved'] == .02
    monkeypatch.setenv('OPENAI_DAILY_RESERVE_USD', '0')
    with pytest.raises(BudgetDenied):budget.reserve('text', 'gpt-4.1-mini')


def test_web_citations_persist_cache_is_owned_and_expires(client, monkeypatch):
    _, a, b = ready(client)
    enable(monkeypatch)
    state = client.app.state.v2
    fake = Client()
    web = WebDiscovery(state['db'], state['memory'], fake)
    request = WebQuery(text='Une exposition à Paris', cloud_consent=True)
    result = web.search(a, request)
    assert result['status'] == 'completed'
    assert result['sources'][0]['url'].startswith('https://www.paris.fr/')
    assert web.search(a, request)['cached'] is True
    assert len(fake.calls) == 1
    assert not web.search(b, request)['cached']
    assert len(fake.calls) == 2
    with state['db'].connect() as c:
        c.execute('UPDATE v2_web_cache SET created_at=?', ((datetime.now(timezone.utc)-timedelta(hours=7)).isoformat(),))
    assert not web.search(a, request)['cached']
    assert len(fake.calls) == 3
    call = fake.calls[0]
    assert call['max_tool_calls'] == 1 and call['store'] is False
    assert call['max_output_tokens'] == 1600
    assert 'PRIVATE_ONBOARDING_SENTINEL' not in call['input']


def test_consent_disabled_quota_and_uncited_response(client, monkeypatch):
    _, a, _ = ready(client)
    state = client.app.state.v2
    fake = Client()
    web = WebDiscovery(state['db'], state['memory'], fake)
    with pytest.raises(ValueError):web.search(a, WebQuery(text='Paris'))
    body = WebQuery(text='Paris', cloud_consent=True)
    assert web.search(a, body)['status'] == 'unavailable'
    assert not fake.calls
    enable(monkeypatch)
    monkeypatch.setenv('OPENAI_DAILY_RESERVE_USD', '0')
    assert web.search(a, body)['reason'] == 'budget_limit_reached'
    assert not fake.calls
    monkeypatch.setenv('OPENAI_DAILY_RESERVE_USD', '1')
    fake.response = SimpleNamespace(model_dump=lambda: {'status':'completed','output':[]})
    assert web.search(a, body)['status'] == 'unavailable'
    with state['db'].connect() as c:
        assert c.execute('SELECT COUNT(*) FROM v2_web_cache').fetchone()[0] == 0
    assert AIBudget(state['db']).status()['total_reserved'] == .1


def test_web_failure_redacts_provider_error(client, monkeypatch):
    _, a, _ = ready(client)
    enable(monkeypatch)
    state = client.app.state.v2
    web = WebDiscovery(state['db'], state['memory'], Client(TimeoutError('SECRET_SENTINEL')))
    result = web.search(a, WebQuery(text='Paris', cloud_consent=True))
    assert result['reason'] == 'provider_timeout'
    assert 'SECRET_SENTINEL' not in json.dumps(result)


def test_new_routes_require_identity_and_consent(client):
    assert client.post(PREFIX+'/discovery/web',json={'text':'Paris','cloud_consent':True}).status_code in (401,403)
    _, a, _ = ready(client)
    assert client.post(PREFIX+'/discovery/web',headers=headers(a),json={'text':'Paris'}).status_code == 422
    result = client.post(PREFIX+'/discovery/web',headers=headers(a),json={'text':'Paris','cloud_consent':True})
    assert result.json()['reason'] == 'not_configured_or_disabled'
    assert client.get(PREFIX+'/ai/budget',headers=headers(a)).json()['total_reserved'] == 0


def test_french_conversation_changes_ranking_without_leaking_or_duplicates(client):
    couple, a, b = ready(client)
    state = client.app.state.v2
    window = {'start':'2026-09-26T18:00:00','end':'2026-09-26T23:59:00'}
    before = state['catalog'].discover(couple['couple_id'],window,limit=100)
    body = {'text':"J'aime le jazz. Je déteste le cinéma.",'privacy_scope':'COUPLE_RECOMMENDATION'}
    first = client.post(PREFIX+'/conversations',headers=headers(a),json=body)
    assert first.status_code == 200
    second = client.post(PREFIX+'/conversations',headers=headers(a),json=body)
    assert {x['id'] for x in first.json()['facts']} == {x['id'] for x in second.json()['facts']}
    context = state['memory'].planning_context(couple['couple_id'])
    assert 'jazz' in context['person_a']['interests']
    assert 'cinema' in context['person_a']['dislikes']
    after = state['catalog'].discover(couple['couple_id'],window,limit=100)
    assert any(x['activity']['category']=='cinema' for x in before)
    assert not any(x['activity']['category']=='cinema' for x in after)
    partner = client.get(PREFIX+'/memories',headers=headers(b)).text
    assert 'discussion:' not in partner
    for fact in first.json()['facts']:
        assert client.delete(PREFIX+'/memories/'+fact['id'],headers=headers(a)).status_code==200
    assert 'cinema' not in state['memory'].planning_context(couple['couple_id'])['person_a']['dislikes']


def test_temporary_conversation_expires_but_exclusion_remains(client):
    couple, a, _ = ready(client)
    state = client.app.state.v2
    old=(datetime.now(timezone.utc)-timedelta(days=60)).isoformat()
    for category,tag,horizon in [('interests','jazz','temporary'),('dislikes','sport','durable')]:
        state['memory'].ingest(couple['couple_id'],'PERSON',a['id'],a['id'],category,'old:'+tag,
            {'values':[tag],'horizon':horizon,'signal_at':old},'COUPLE_RECOMMENDATION','conversation')
    profile=state['memory'].planning_context(couple['couple_id'])['person_a']
    assert 'jazz' not in profile['interests']
    assert 'sport' in profile['dislikes']
