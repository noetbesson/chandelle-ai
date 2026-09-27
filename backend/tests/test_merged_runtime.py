"""Cross-branch contracts: actual app state, imported data and the voice endpoint."""
from datetime import datetime, timezone
from backend.tests.test_api import client, ready, headers, answer, offline_only
from backend.tests.test_imported_catalog import bundle, venue
from backend.tests.test_web_pipeline import fact
from backend.streams.C_discovery.local_catalog import ImportedCatalog
from backend.streams.C_discovery.service import record_web
from backend.streams.C_discovery.recommendations import DatabaseActivities


def test_imported_catalog_reaches_discover_and_voice_without_cloud(client, tmp_path):
    pair, a, b = ready(client)
    state = client.app.state.v2
    ImportedCatalog(state['db']).import_bundle(bundle(tmp_path, [venue()]))
    status = client.get('/api/v2/integrations').json()
    assert status['catalog']['mode'] == 'imported_and_web'
    assert status['catalog']['records'] == 1
    assert status['dialogue']['requires_consent'] is True
    assert 'providers' in status['calendar']
    assert 'dialogue' in state and 'real_recommendations' in state
    response = client.get('/api/v2/activities/real', params={'query':'japonais','category':'food'}, headers=headers(a))
    assert response.status_code == 200
    idea = response.json()['items'][0]
    assert idea['source'] == idea['attribution'] == 'tripadvisor'
    assert idea['price_per_person'] is None and idea['start'] is None
    response = client.post('/api/v2/ask/chat', headers=headers(a), json={
        'message':'Un restaurant japonais à Paris', 'request_id':'imported-voice', 'cloud_consent':False})
    assert response.status_code == 200
    result = response.json()
    assert result['mode'] == 'offline' and result['suggestions'][0]['id'] == idea['id']
    assert result['plans'] == []
    assert answer(client,pair,b,3,{'values':['japonais']}).status_code == 200
    assert client.get('/api/v2/activities/real',params={'query':'japonais'},headers=headers(a)).json()['items'] == []


def test_voice_adapter_does_not_claim_proposed_visiting_hours_are_published():
    proposed = record_web(fact(0),datetime.now(timezone.utc).isoformat())
    assert proposed['schedule_status'] == 'proposed'
    idea = DatabaseActivities.adapt(proposed)
    assert idea['kind'] == 'place' and idea['start'] is None and idea['end'] is None
    proposed.update(kind='event',schedule_status='published')
    event = DatabaseActivities.adapt(proposed)
    assert event['kind'] == 'event' and event['start'] == proposed['starts_at']
