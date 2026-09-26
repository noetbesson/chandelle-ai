"""Fake Responses API contract tests: never construct a network client."""
import json
from types import SimpleNamespace

import pytest

from backend.integrations.openai import (
    Conflict, Explanation, Extraction, OpenAIAdapter, ParsedRequest, Ranking,
)


class FakeClient:
    def __init__(self, output=None, failure=None):
        self.output = output
        self.failure = failure
        self.calls = []
        self.responses = self
        self.embeddings = self

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.failure:
            raise self.failure
        return SimpleNamespace(output_parsed=self.output)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.failure:
            raise self.failure
        return SimpleNamespace(data=[SimpleNamespace(embedding=[.25, -.5, .75])])


@pytest.mark.parametrize('method,args,output,schema', [
    ('parse', ('a quiet evening',), {'budget': 70, 'categories':['culture'], 'excluded':[]}, ParsedRequest),
    ('extract', ('I enjoy art', 'owner-a'), {'facts':[{'category':'interests','value':'art','confidence':.9}]}, Extraction),
    ('classify', ('old','new'), {'classification':'supersedes'}, Conflict),
    ('explain', ([{'id':'a','title':'Demo'}],), {'candidate_ids':['a'],'explanation':'An available internal activity.'}, Explanation),
    ('rerank', ([{'id':'a'},{'id':'b'}],), {'candidate_ids':['b','a']}, Ranking),
])
def test_structured_outputs(method, args, output, schema, monkeypatch):
    monkeypatch.setenv('OPENAI_MODEL', 'configured-test-model')
    client = FakeClient(output)
    adapter = OpenAIAdapter(client=client, enabled=True)
    result = getattr(adapter, method)(*args)
    assert isinstance(result, schema)
    assert adapter.last_mode == 'openai'
    call = client.calls[0]
    assert call['model'] == 'configured-test-model'
    assert call['text_format'] is schema
    assert call['store'] is False
    assert call['timeout'] == 12


@pytest.mark.parametrize('bad', [None, {'budget': -1}, {'budget': 30, 'unknown': 'field'}, {'categories':'wrong type'}])
def test_malformed_structured_output_falls_back(bad):
    adapter = OpenAIAdapter(FakeClient(bad), enabled=True)
    result = adapter.parse('food under 40 no cinema')
    assert result.budget == 40
    assert result.categories == ['food']
    assert result.excluded == ['cinema']
    assert adapter.last_mode == 'offline'
    assert adapter.last_fallback == 'provider_unavailable_or_invalid_output'


@pytest.mark.parametrize('method', ['rerank','explain'])
@pytest.mark.parametrize('ids', [['invented'], ['a','a'], ['a','invented']])
def test_unknown_and_duplicate_candidate_ids_rejected(method, ids):
    output = {'candidate_ids': ids}
    if method == 'explain':
        output['explanation'] = 'Untrusted provider response'
    adapter = OpenAIAdapter(FakeClient(output), enabled=True)
    result = getattr(adapter, method)([{'id':'a'},{'id':'b'}])
    assert result.candidate_ids == ['a','b']
    assert adapter.last_mode == 'offline'
    assert adapter.last_fallback == 'provider_unavailable_or_invalid_output'


def test_timeout_fallback_never_logs_private_prompt_or_key(caplog, capsys, monkeypatch):
    secret = 'test-private-secret-sentinel'
    monkeypatch.setenv('OPENAI_API_KEY', secret)
    adapter = OpenAIAdapter(FakeClient(failure=TimeoutError(secret)), enabled=True)
    result = adapter.extract(f'I love {secret}', 'owner-a')
    assert result.facts[0].value == secret
    assert adapter.last_mode == 'offline'
    assert secret not in json.dumps(adapter.status())
    assert secret not in str(adapter.last_fallback)
    assert secret not in caplog.text
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err


def test_disabled_adapter_makes_no_client_calls_even_with_key(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-present-but-disabled')
    client = FakeClient(failure=AssertionError('No provider requests allowed'))
    adapter = OpenAIAdapter(client, enabled=False)
    assert adapter.parse('budget 20').budget == 20
    assert adapter.extract('I hate crowds', 'a').facts[0].category == 'dislikes'
    assert adapter.classify('x','x').classification == 'equivalent'
    assert adapter.rerank([{'id':'a'}]).candidate_ids == ['a']
    assert adapter.explain([{'id':'a'}]).candidate_ids == ['a']
    assert adapter.embed('private text') is None
    assert not client.calls
    assert adapter.status()['available'] is False


def test_owner_scoped_extraction_has_no_previous_person_context():
    client = FakeClient({'facts':[]})
    adapter = OpenAIAdapter(client, enabled=True)
    adapter.extract('A PRIVATE SENTINEL', 'person-a')
    adapter.extract('B PRIVATE SENTINEL', 'person-b')
    first, second = [json.loads(call['input']) for call in client.calls]
    assert first['owner_id'] == 'person-a'
    assert second['owner_id'] == 'person-b'
    assert 'A PRIVATE SENTINEL' not in client.calls[1]['input']
    assert 'person-a' not in client.calls[1]['input']


def test_explanation_drops_all_private_context_and_catalog_extra_fields():
    client = FakeClient(Explanation(candidate_ids=['a'], explanation='A compatible activity'))
    adapter = OpenAIAdapter(client, enabled=True)
    adapter.explain([{'id':'a','title':'Demo','person_a_score':.8,'person_b_score':.7,
                      'private_memory':'NEVER SEND'}], context={'person_a':{'private':'NEVER SEND'}})
    payload = json.loads(client.calls[0]['input'])
    assert 'NEVER SEND' not in client.calls[0]['input']
    assert payload['candidates'][0] == {'id':'a','title':'Demo','person_a_score':.8,'person_b_score':.7}


def test_embedding_model_configuration_and_fallback(monkeypatch):
    monkeypatch.setenv('OPENAI_EMBEDDING_MODEL','configured-embedding-test')
    client = FakeClient()
    adapter = OpenAIAdapter(client, enabled=True)
    assert adapter.embed('consented text') == [.25,-.5,.75]
    assert client.calls[0]['model'] == 'configured-embedding-test'
    failed = OpenAIAdapter(FakeClient(failure=TimeoutError()), enabled=True)
    assert failed.embed('consented text') is None


def test_enabled_without_key_remains_offline(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    adapter = OpenAIAdapter(enabled=True)
    assert adapter.status()['available'] is False
    assert adapter.parse('culture below 60').budget == 60
    assert adapter._client is None
