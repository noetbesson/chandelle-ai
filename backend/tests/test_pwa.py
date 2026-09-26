"""Public PWA delivery does not add an unauthenticated memory write endpoint."""
import json
from backend.tests.test_api import client,offline_only

def test_manifest_worker_and_receiver(client):
    manifest=client.get('/manifest.json')
    assert manifest.status_code==200 and 'application/manifest+json' in manifest.headers['content-type']
    value=manifest.json();target=value['share_target']
    assert value['scope']=='/' and value['display']=='standalone'
    assert target['action']=='/api/receive-share' and target['method']=='POST'
    assert target['enctype']=='multipart/form-data' and target['params']['files'][0]['name']=='video'
    for icon in value['icons']:
        r=client.get(icon['src']);assert r.status_code==200 and r.content[:8]==b'\x89PNG\r\n\x1a\n'
    worker=client.get('/sw.js');assert worker.status_code==200 and worker.headers['service-worker-allowed']=='/'
    assert "url.pathname==='/api/receive-share'" in worker.text
    assert 'share-store.mjs' in worker.text
    for url in ('/partager','/installer'):
        r=client.get(url);assert r.status_code==200 and '/manifest.json' in r.text
    assert client.get('/partager').headers['cache-control']=='no-store'
    assert '/manifest.json' in client.get('/').text

def test_no_worker_fallback_never_stores_anonymous_data(client):
    r=client.post('/api/receive-share',data={'text':'PRIVATE SHARED PAYLOAD'})
    assert r.status_code==409 and 'PRIVATE SHARED PAYLOAD' not in r.text
    assert r.headers['cache-control']=='no-store'
    with client.app.state.v2['db'].connect() as c:
        assert c.execute('SELECT COUNT(*) FROM v2_reel_jobs').fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM v2_facts').fetchone()[0]==0
