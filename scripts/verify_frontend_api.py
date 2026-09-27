"""Run actual frontend-shaped payloads through local FastAPI, without sockets."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from backend.api.app import create_app
from backend.tests.web_provider import install
from pytest import MonkeyPatch


def main():
    with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'.runtime') as directory, MonkeyPatch.context() as patch:
        app=create_app(Path(directory)/'ui.sqlite')
        install(app,patch)
        client=TestClient(app)
        assert client.get('/app').status_code == 200
        assert client.get('/v2-static/app.mjs').status_code == 200
        font = client.get('/v2-static/public/fonts/Conjiote%20Personal%20Use.otf')
        assert font.status_code == 200 and font.content.startswith(b'OTTO')
        assert font.content == (Path(__file__).resolve().parents[1] / 'font/Conjiote Personal Use.otf').read_bytes()
        for asset in ['chandelier.mjs', 'discover.mjs', 'icons.mjs', 'visuals.mjs', 'vendor/motion-13.4.4.js']:
            response = client.get('/v2-static/' + asset)
            assert response.status_code == 200 and 'no-store' in response.headers['cache-control'], asset
        pair = client.post('/api/v2/onboarding/couples', json={'person_a': 'Alex', 'person_b': 'Blair'}).json()
        cid = pair['couple_id']
        for member in pair['members']:
            headers = {'X-Member-Token': member['token']}
            base = f"/api/v2/onboarding/couples/{cid}/members/{member['id']}"
            answers = [
                {'name': member['name'], 'pronouns': ''},
                {'values': ['food', 'culture']}, {'values': []},
                {'min': 15, 'max': 70, 'flexible': False, 'unit': 'person'},
                {'energy': .5, 'social': .5, 'novelty': .5, 'outdoor': .5, 'duration': .5},
                {'days': [], 'travel_minutes': 40, 'dietary': [], 'accessibility': []},
                {'text': 'A quiet gallery date was lovely'},
            ]
            for step, value in enumerate(answers, 1):
                result = client.put(base + '/answers', headers=headers, json={'step': step, 'value': value, 'privacy_scope': 'PRIVATE' if step == 7 else 'COUPLE_RECOMMENDATION'})
                assert result.status_code == 200, result.text
            assert client.post(base + '/complete', headers=headers, json={}).status_code == 200
        routes = ['/suggestions', '/date-plans', f'/couples/{cid}/profile', '/integrations', '/health', '/activities?query=&category=&limit=60', f"/profiles/PERSON/{member['id']}", f"/memories?scope=PERSON&entity_id={member['id']}", '/history']
        for route in routes:
            result = client.get('/api/v2' + route, headers=headers)
            assert result.status_code == 200, (route, result.text)
        result = client.post('/api/v2/recommendations/query', headers=headers, json={'time_window': {'start':'2026-10-02T18:00:00+02:00','end':'2026-10-03T00:00:00+02:00'}, 'text': 'A thoughtful relaxed date', 'categories': [], 'activity_count': 2, 'max_plans': 3, 'mode': 'auto', 'radius_km': 15})
        assert result.status_code == 200, result.text
        plan = result.json()['plans'][0]
        selected = plan['activities'][0]['id']
        selected_result = client.post('/api/v2/recommendations/query', headers=headers, json={'time_window': {'start':'2026-10-02T18:00:00+02:00','end':'2026-10-03T00:00:00+02:00'}, 'text': 'Include our selected activity', 'required_activity_id': selected, 'activity_count': 2, 'mode': 'auto'})
        assert selected_result.status_code == 200, selected_result.text
        assert all(selected in [a['id'] for a in p['activities']] for p in selected_result.json()['plans'])
        assert client.patch('/api/v2/date-plans/' + plan['id'], headers=headers, json={'status': 'accepted'}).status_code == 200
        result = client.post('/api/v2/date-plans/' + plan['id'] + '/feedback', headers=headers, json={'rating': 5, 'activity_ratings': {}, 'text': 'Loved the relaxed evening', 'repeat': [plan['activities'][0]['category']], 'avoid': [], 'privacy_scope': 'PRIVATE', 'idempotency_key': 'ui-flow'})
        assert result.status_code == 200, result.text
        fact = client.get(f"/api/v2/memories?scope=PERSON&entity_id={member['id']}", headers=headers).json()['items'][0]
        result = client.patch('/api/v2/memories/' + fact['id'], headers=headers, json={'category': fact['category'], 'value': fact['value'], 'privacy_scope': fact['privacy_scope']})
        assert result.status_code == 200, result.text
        print('Frontend payload integration: static assets, 14 interview answers, 2 completions, 9 screen endpoints, simulated web query, selected activity inclusion, accept, category review, memory edit PASS')


if __name__ == '__main__':
    main()
