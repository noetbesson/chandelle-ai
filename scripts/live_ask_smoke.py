"""Explicit, bounded Ask check with synthetic people and a disposable database.

Never included in check.sh. Uses OpenAI; --web also checks automatic web research.
"""
import os
from pathlib import Path
import sys
import tempfile
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--web',action='store_true',help='Test Paris 14 / 40 EUR, with live web research.')
    args=parser.parse_args()
    if os.getenv('RUN_LIVE_OPENAI_SMOKE') != '1':
        raise SystemExit('Set RUN_LIVE_OPENAI_SMOKE=1 explicitly. Paid API check: at most four text calls and, with --web, four bounded web requests.')
    from scripts.run_local import load_environment
    os.environ.update(load_environment(Path(os.getenv('CHANDELLE_ENV_FILE', ROOT / '.env')), os.environ))
    if os.getenv('OPENAI_ENABLED') != '1' or not os.getenv('OPENAI_API_KEY'):
        raise SystemExit('Configure OPENAI_ENABLED=1 and OPENAI_API_KEY in the local .env.')
    os.environ.update(GRADIUM_ENABLED='0', OPENAI_WEB_ENABLED='1' if args.web else '0', PROACTIVE_SCHEDULER_ENABLED='0')
    with tempfile.TemporaryDirectory(prefix='chandelle-ask-live-') as directory:
        os.environ['CHANDELLE_DB_PATH'] = str(Path(directory) / 'test.sqlite3')
        from backend.api.app import create_app
        from backend.streams.C_discovery.local_catalog import ImportedCatalog
        from fastapi.testclient import TestClient
        app = create_app(os.environ['CHANDELLE_DB_PATH'])
        ImportedCatalog(app.state.v2['db']).import_bundle()
        with TestClient(app) as client:
            pair = client.post('/api/v2/onboarding/couples', json={'person_a':'Smoke Alex','person_b':'Smoke Sam'}).json()
            for member in pair['members']:
                auth = {'X-Member-Token':member['token']}
                path = f'/api/v2/onboarding/couples/{pair["couple_id"]}/members/{member["id"]}'
                for step in range(1, 8):
                    value = {'name':member['name']} if step == 1 else {'skip':True}
                    client.put(path + '/answers', headers=auth, json={'step':step,'value':value,'privacy_scope':'PRIVATE'}).raise_for_status()
                client.post(path + '/complete', headers=auth).raise_for_status()
            previous = {}
            for i, text in enumerate([
                'resto paris 14 budget 40€ max' if args.web else 'Un restaurant japonais à Paris pour deux, avec un budget de 80 euros.',
                'Pourquoi ces adresses ? Compare-les selon les informations dont tu disposes, sans nouvelle recherche.',
            ]):
                response = client.post('/api/v2/ask/chat', headers=auth, json={
                    'message':text,'request_id':f'live-ask-{i}','cloud_consent':True,'web_consent':args.web,
                    'session_id':previous.get('session_id'),'revision':previous.get('revision',0)})
                result = response.json()
                if response.status_code != 200 or result.get('mode') != 'openai':
                    reason = result.get('error', {}).get('code') or result.get('fallback') or 'invalid_response'
                    raise SystemExit('Ask live check failed: ' + reason)
                if not result.get('suggestions'):
                    raise SystemExit('Ask live check failed: no sourced suggestion.')
                if result['intent']['budget'] != (40 if args.web else 80):
                    raise SystemExit('Ask live check failed: conversation budget not preserved.')
                if args.web:
                    if len(result['suggestions'])<3:
                        print('Retrieval diagnostics:', result.get('retrieval'))
                        print('Web diagnostics:',{k:v for k,v in result.get('web',{}).items() if k.endswith('_count') or k=='reason'})
                        with app.state.v2['db'].connect() as c:
                            import json
                            for r in c.execute("SELECT payload FROM v2_activities WHERE json_extract(payload,'$.provider')='openai_web'"):
                                row=json.loads(r[0])
                                print({k:row.get(k) for k in ('title','address','price_per_person','source_url')})
                        raise SystemExit('Ask live check failed: fewer than three suggestions.')
                    from backend.streams.C_discovery.locations import matches_location
                    assert all(matches_location('Paris 14e',a['location']['address'],a['location']['arrondissement']) for a in result['suggestions'])
                    assert all(a['total_couple_cost'] is None or a['total_couple_cost']<=40 for a in result['suggestions'])
                print(f'Tour {i+1} · OpenAI · {len(result["suggestions"])} fiches sourcées')
                print(result['reply'])
                if args.web and i==0:
                    for item in result['suggestions']:
                        print(item['name'],item['location']['address'],item['total_couple_cost'],item['website'])
                        print(item.get('description'))
                previous = result
            client.delete('/api/v2/ask/chat/' + previous['session_id'], headers=auth).raise_for_status()
        print('PASS · Ask complet, contexte conservé, base personnelle intacte, aucun appel Gradium. Web : '+str(args.web))


if __name__ == '__main__':
    main()
