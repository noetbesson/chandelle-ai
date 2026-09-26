"""Speech contracts against a fake provider; no real audio or provider calls."""
import io
import json
import wave

import httpx
import pytest

from backend.tests.test_api import client, ready, create, headers, offline_only
from backend.integrations.gradium import GradiumAdapter


def wav():
    output = io.BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(24000)
        audio.writeframes(b'\0\0' * 2400)
    return output.getvalue()


def provider(monkeypatch, handler):
    monkeypatch.setenv('GRADIUM_ENABLED', '1')
    monkeypatch.setenv('GRADIUM_API_KEY', 'fake-test-key')
    monkeypatch.setenv('GRADIUM_VOICE_ID', 'test-voice')
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


def test_voice_requires_identity_and_completed_interviews(client):
    for path, body in [('/discover/chat', {}), ('/voice/speak', {'text': 'bonjour'})]:
        assert client.post('/api/v2' + path, json=body).status_code == 403
    assert client.post('/api/v2/voice/transcribe', content=wav()).status_code == 403
    pair = create(client)
    for path, body in [('/discover/chat', {}), ('/voice/speak', {'text': 'bonjour'})]:
        assert client.post('/api/v2' + path, headers=headers(pair['members'][0]), json=body).status_code == 409


def test_gradium_unconfigured_and_opt_in(client, monkeypatch):
    monkeypatch.setenv('GRADIUM_ENABLED', '0')
    monkeypatch.setenv('GRADIUM_API_KEY', 'fake-test-key')
    monkeypatch.setenv('GRADIUM_VOICE_ID', 'test-voice')
    _, a, _ = ready(client)
    status = client.get('/api/v2/integrations').json()['gradium']
    assert status == {'enabled': False, 'configured': True, 'available': False}
    assert 'fake-test-key' not in json.dumps(status)
    r = client.post('/api/v2/voice/speak', headers=headers(a), json={'text': 'bonjour'})
    assert r.status_code == 503


def test_transcription_wire_contract_and_no_audio_persistence(client, monkeypatch):
    _, a, _ = ready(client)
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.path == '/api/post/speech/asr'
        assert request.headers['x-api-key'] == 'fake-test-key'
        assert request.headers['content-type'] == 'audio/wav'
        assert request.content == wav()
        assert json.loads(request.url.params['json_config'])['language'] == 'fr'
        return httpx.Response(200, text='{"type":"text","text":"Une balade"}\n{"type":"end_text"}\n{"type":"text","text":"pour deux"}\n')
    provider(monkeypatch, handler)
    r = client.post('/api/v2/voice/transcribe', headers={**headers(a), 'Content-Type': 'audio/wav'}, content=wav())
    assert r.status_code == 200 and r.json()['text'] == 'Une balade pour deux'
    assert len(calls) == 1
    with client.app.state.v2['db'].connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM v2_messages').fetchone()[0] == 0


def test_tts_wire_contract(client, monkeypatch):
    _, a, _ = ready(client)
    def handler(request):
        assert request.url.path == '/api/post/speech/tts'
        body = json.loads(request.content)
        assert body['voice_id'] == 'test-voice' and body['only_audio'] is True
        assert body['output_format'] == 'wav' and body['text'] == 'Bonjour'
        return httpx.Response(200, content=wav(), headers={'content-type': 'audio/wav'})
    provider(monkeypatch, handler)
    response = client.post('/api/v2/voice/speak', headers=headers(a), json={'text': 'Bonjour'})
    assert response.status_code == 200 and response.content == wav()
    assert response.headers['cache-control'] == 'private, no-store'


@pytest.mark.parametrize('code,body', [(429, 'fake-test-key private provider error'), (200, '{"type":"error","message":"private"}'), (200, 'bad-json')])
def test_provider_errors_are_sanitized(client, monkeypatch, code, body):
    _, a, _ = ready(client)
    provider(monkeypatch, lambda request: httpx.Response(code, text=body))
    response = client.post('/api/v2/voice/transcribe', headers={**headers(a), 'Content-Type': 'audio/wav'}, content=wav())
    assert response.status_code == 503
    assert 'fake-test-key' not in response.text and 'private' not in response.text


def test_invalid_audio_rejected_before_provider(client, monkeypatch):
    _, a, _ = ready(client)
    def no_call(*args, **kwargs):
        raise AssertionError('Malformed audio must not reach Gradium')
    monkeypatch.setattr(GradiumAdapter, '_post', no_call)
    assert client.post('/api/v2/voice/transcribe', headers=headers(a), content=b'bad').status_code == 415
    assert client.post('/api/v2/voice/transcribe', headers={**headers(a), 'Content-Type': 'audio/wav'}, content=b'bad').status_code == 422
    assert client.post('/api/v2/voice/transcribe', headers={**headers(a), 'Content-Type': 'audio/wav'}, content=b'x' * 4_500_001).status_code == 413


def test_guided_chat_produces_real_private_scoped_plan(client):
    _, a, _ = ready(client)
    other_pair = ready(client)
    h = headers(a)
    greeting = client.post('/api/v2/discover/chat', headers=h, json={}).json()
    assert greeting['plans'] == [] and 'sortie' in greeting['reply']
    question = client.post('/api/v2/discover/chat', headers=h, json={'messages': ['Une balade']}).json()
    assert 'budget' in question['reply']
    result = client.post('/api/v2/discover/chat', headers=h, json={'messages': ['Une sortie pour deux', '140 euros pour deux', 'Rien à éviter']})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['plans'], data
    plan = data['plans'][0]
    assert plan['total_couple_cost'] <= 140
    assert client.get('/api/v2/date-plans/' + plan['id'], headers=h).status_code == 200
    assert client.get('/api/v2/date-plans/' + plan['id'], headers=headers(other_pair[1])).status_code == 404
    with client.app.state.v2['db'].connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM v2_messages').fetchone()[0] == 0
    assert 'PRIVATE_ONBOARDING_SENTINEL' not in result.text


def test_dialogue_bounds_and_no_feasible_plan(client):
    _, a, _ = ready(client)
    assert client.post('/api/v2/discover/chat', headers=headers(a), json={'messages': ['x'] * 9}).status_code == 422
    for person in [a]:
        assert client.put('/api/v2/availability', headers=headers(person), json={'slots': []}).status_code == 200
    result = client.post('/api/v2/discover/chat', headers=headers(a), json={'messages': ['Une balade'], 'recommend': True}).json()
    assert result['plans'] == [] and 'disponibilités' in result['reply']
