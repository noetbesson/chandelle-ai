"""Real SQLite/API tests; tiny source records simulate exports, providers never called."""
import gzip
import json
from pathlib import Path

import pytest

from backend.db import Database
from backend.streams.C_discovery.import_normalize import record, advertised_dates
from backend.streams.C_discovery.local_catalog import ImportedCatalog
from backend.integrations.openai import OpenAIAdapter
from backend.tests.test_api import client, ready, headers, offline_only


def venue(index=1, **changes):
    row = {'BMQDV href': f'https://www.tripadvisor.com/Restaurant_Review-g187147-d{index}-Reviews-Test-Paris_Ile_de_France.html',
           'biGQs': f'{index}. Restaurant Japonais {index}', 'biGQs 2': '4.5', 'biGQs 3': '(1,234 reviews)',
           'biGQs 4': 'Japanese, Sushi', 'biGQs 5': '$$ - $$$', 'biGQs 6': 'Open now', **changes}
    return record(row, 'Medium priced restaurant.xlsx', 'Sheet1', index + 1)


def bundle(tmp_path, values):
    path = tmp_path / 'sources.jsonl.gz'
    path.write_bytes(gzip.compress('\n'.join(json.dumps(v) for v in values).encode(), mtime=0))
    return path


def test_normalization_keeps_source_claims_without_inventing_times_prices_or_locality():
    v = venue()
    assert v['title'] == 'Restaurant Japonais 1'
    assert v['price_tier'] == 'moderate' and v['review_count'] == 1234
    assert {'japanese', 'japonais'} <= set(v['tags'])
    assert v['last_verified_at'] is None and v['source_observed_at'] is None
    assert 'Open now' not in json.dumps(v)
    assert v['provenance'] == [['Medium priced restaurant.xlsx', 'Sheet1', 2]]
    outside = venue(**{'BMQDV href': 'https://www.tripadvisor.com/Restaurant_Review-g187265-d8-Reviews-Test-Lyon.html'})
    assert outside['department'] is None and outside['eligibility'] == 'needs_location'
    assert record({'BMQDV href': 'javascript:alert(1)', 'biGQs': 'malicious'}, 'Café.xlsx', 'Sheet1', 1) is None


@pytest.mark.parametrize('value,result', [
    ('du 19 au 20 septembre 2026', ('2026-09-19', '2026-09-20')),
    ('Du 30 septembre au 2 octobre 2026.', ('2026-09-30', '2026-10-02')),
    ('le 27 septembre 2026', ('2026-09-27', '2026-09-27')),
    ('demain et le 2 octobre', (None, None)),
    ('le 31 février 2026', (None, None)),
    ('du 3 au 4 mai 2026 et du 8 au 9 juin 2026', (None, None)),
])
def test_dates_never_assume_missing_year_or_relative_dates(value, result):
    assert advertised_dates(value) == result


def test_film_is_a_reference_and_release_is_not_a_screening():
    r = record({'meta-title-link href': 'https://www.allocine.fr/film/fichefilm_gen_cfilm=5.html',
                'meta-title-link': 'Film', 'meta-body-item': '1h 38min', 'date': '9 septembre 2026',
                'xXx': 'Drame', 'xXx href 2': 'https://www.allocine.fr/films/genre-13008/'},
               'allocine.xlsx', 'Sheet1', 2)
    assert r['kind'] == 'film' and r['eligibility'] == 'reference'
    assert r['release_date'] == '2026-09-09' and r['film_duration_minutes'] == 98
    assert r['start_date'] is None and r['department'] is None
    assert r['tags'] == ['Drame']


def test_import_idempotence_update_rollback_and_fts(tmp_path):
    catalog = ImportedCatalog(Database(tmp_path / 'db.sqlite3'))
    path = bundle(tmp_path, [venue(i) for i in range(1, 4)])
    first = catalog.import_bundle(path)
    assert first['inserted'] == 3
    assert catalog.import_bundle(path)['unchanged']
    assert len(catalog.search('un japonais', ['food'])) == 3
    assert len(catalog.search('japonais " OR * --', ['food'])) == 3
    original = catalog.search('japonais')[0]['imported_at']
    path = bundle(tmp_path, [venue(1, **{'biGQs 5': '$'})])
    assert catalog.import_bundle(path)['updated'] == 1
    assert catalog.status()['records'] == 3  # Partial export must never delete the catalogue.
    found = next(v for v in catalog.search('japonais') if v['id'] == 'tripadvisor:1')
    assert found['price_tier'] == 'budget' and found['imported_at'] == original
    assert found['price_per_person'] is None and found['checked_at'] is None
    bad = bundle(tmp_path, [venue(1), venue(1)])
    with pytest.raises(ValueError): catalog.import_bundle(bad)
    assert catalog.status()['records'] == 3
    with catalog.db.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM v2_activity_search').fetchone()[0] == 3


def test_expired_articles_and_films_never_become_available_outings(tmp_path):
    catalog = ImportedCatalog(Database(tmp_path / 'db.sqlite3'))
    article = record({'col-xs-12 href': 'https://www.sortiraparis.com/arts-culture/articles/42-sortie',
                      'col-xs-12 2': 'Festival à Paris', 'col-xs-12': 'Du 19 au 20 septembre 2000 à Paris.'},
                     'Sortir à paris.xlsx', 'Activité', 3)
    catalog.import_bundle(bundle(tmp_path, [article, venue()]))
    assert catalog.status()['records'] == 2 and catalog.status()['searchable'] == 1
    assert not catalog.search('festival', ['culture'])
    assert catalog.search('festival', ['culture'], references=True)


def install_sources(client, tmp_path):
    ImportedCatalog(client.app.state.v2['db']).import_bundle(bundle(tmp_path, [venue(i) for i in range(1, 5)]))


def test_import_reaches_same_cards_with_no_provider_and_no_fake_plan(client, monkeypatch, tmp_path):
    couple, member, partner = ready(client)
    install_sources(client, tmp_path)
    def no_web(*a, **kw): raise AssertionError('Enough local candidates, must not use web')
    monkeypatch.setattr(client.app.state.v2['planning'].web, 'search', no_web)
    response = client.post('/api/v2/dates/search', headers=headers(member), json={
        'constraints': {'text': 'restaurant japonais', 'mode': 'offline', 'activity_count': 1}})
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data['activities']) == 4 and not data['proposals']
    card = data['activities'][0]
    assert card['source_kind'] == 'import' and card['price_tier'] == 'moderate'
    assert card['start'] is None and card['checked_at'] is None and not card['composable']
    assert client.get('/api/v2/runs/' + data['search_id'], headers=headers(partner)).status_code == 403
    assert client.post('/api/dates/compose', headers=headers(member), json={
        'search_id': data['search_id'], 'selected_activity_ids': [card['id']]}).status_code == 422
    assert next(t for t in data['trace'] if t['stage'] == 'web_search')['tool_calls'] == 0


def test_web_failure_preserves_imports_and_enrichment_receives_only_shortlist(client, monkeypatch, tmp_path):
    _, member, _ = ready(client)
    install_sources(client, tmp_path)
    from backend.tests.test_web_pipeline import START
    seen = []
    def failed(member, body):
        seen.extend(body.local_references)
        return {'status': 'unavailable', 'reason': 'provider_timeout', 'activities': [], 'raw_count': 0}
    monkeypatch.setattr(client.app.state.v2['planning'].web, 'search', failed)
    response = client.post('/api/v2/dates/search', headers=headers(member), json={
        'constraints': {'text': 'restaurant japonais ce soir', 'mode': 'auto', 'activity_count': 1,
                        'time_window': {'start': START.isoformat(), 'end': START.replace(hour=23).isoformat()}}})
    data = response.json()
    assert response.status_code == 200, response.text
    assert data['status'] == 'completed' and len(data['activities']) == 4
    assert 0 < len(seen) <= 8 and all(set(r) == {'name', 'category', 'source_url', 'kind'} for r in seen)
    assert any('vérification web' in w for w in data['warnings'])


def test_explicit_exclusion_still_applies_to_imports(client, tmp_path):
    _, member, _ = ready(client)
    install_sources(client, tmp_path)
    data = client.post('/api/v2/dates/search', headers=headers(member), json={
        'constraints': {'text': 'restaurant sans japonais', 'mode': 'offline'}}).json()
    assert not data['activities'] and data['message']
    assert any(t['stage'] == 'import_explicit_exclusions' and t['removed'] == 4 for t in data['trace'])


def test_web_enrichment_can_compose_without_duplicating_import_or_changing_its_claims(client, monkeypatch, tmp_path):
    _, member, _ = ready(client)
    install_sources(client, tmp_path)
    from backend.tests.test_web_pipeline import configure, fact, START
    url = venue(1)['source_url'].replace('tripadvisor.com', 'tripadvisor.fr').replace('-Reviews-Test-', '-Reviews-Renamed-')
    provider = configure(client, monkeypatch, [fact(source_url=url)])
    response = client.post('/api/v2/dates/search', headers=headers(member), json={
        'constraints': {'text': 'restaurant japonais ce soir', 'mode': 'auto', 'activity_count': 1, 'categories': ['food'],
                        'time_window': {'start': START.isoformat(), 'end': START.replace(hour=23).isoformat()}}})
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data['activities']) == 4 and len(data['proposals']) == 1
    assert sum(a['source_kind'] == 'web' for a in data['activities']) == 1
    imported = client.app.state.v2['catalog'].get('tripadvisor:1')
    assert imported['price_per_person'] is None and imported['last_verified_at'] is None
    assert len(provider.calls) == 1


def test_developer_reset_does_not_corrupt_fts(client, monkeypatch, tmp_path):
    install_sources(client, tmp_path)
    monkeypatch.setenv('CHANDELLE_DEV', '1')
    assert client.post('/api/v2/dev/reset', json={'confirmation': 'RESET LOCAL V2'}).status_code == 200
    install_sources(client, tmp_path)
    assert len(ImportedCatalog(client.app.state.v2['db']).search('japonais')) == 4


def bar(index=1, **changes):
    return record({'BarGrid_cardLink__NF2Km href': f'https://www.mistergoodbeer.com/bars/test-{index}',
                   'BarGrid_barName__ggBLd': f'Bar {index}', 'BarGrid_address__a3r3v': '42 Rue de Rochechouart, 75009 Paris, France',
                   'BarGrid_mediaBadge__udk9e': '1,00 €', 'BarGrid_ratingSummary__Km40k': '4,5',
                   'BarGrid_ratingCount__TVP0T': '(12 avis)', 'BarTags_tag_design__gliEq': 'Petite terrasse',
                   'BarTags_tag_design__gliEq 2': 'Karaoké', 'BarTags_tag_design__gliEq 3': 'Pinte à partir de 5,00 €',
                   'BarGrid_dealText__MxiVc': 'Sur présentation de l’application avant 20h', **changes},
                  'Bar.xlsx', 'Sheet1', index + 3)


def test_bars_keep_units_address_and_conditional_claims():
    v = bar()
    assert v['source_name'] == 'mistergoodbeer' and v['id'] == 'mistergoodbeer:test-1'
    assert v['category'] == 'nightlife' and v['department'] == '75' and v['city'] == 'Paris'
    assert v['pint_price_from_eur'] == 5 and v['price_tier'] is None
    assert v['rating'] == 4.5 and v['review_count'] == 12
    assert v['offer_note'] == 'Sur présentation de l’application avant 20h'
    assert v['last_verified_at'] is None
    assert bar(**{'BarTags_tag_design__gliEq 3': ''})['pint_price_from_eur'] is None  # Badge alone has no unit.
    assert bar(**{'BarGrid_address__a3r3v': '4 Rue du Test, 69001 Lyon, France'})['eligibility'] == 'needs_location'
    assert bar(**{'BarGrid_cardLink__NF2Km href': 'https://sortiraparis.com/bars/test'}) is None


def test_bar_import_is_idempotent_and_terrace_query_rejects_absence(tmp_path):
    catalog = ImportedCatalog(Database(tmp_path / 'bars.sqlite3'))
    path = bundle(tmp_path, [bar(), bar(2, **{'BarTags_tag_design__gliEq': 'Pas de terrasse'}), venue()])
    assert catalog.import_bundle(path)['inserted'] == 3
    assert catalog.import_bundle(path)['unchanged']
    found = catalog.search('bar terrasse', ['nightlife'])
    assert len(found) == 1 and found[0]['id'] == 'mistergoodbeer:test-1'
    assert found[0]['address'].startswith('42 Rue')
    assert found[0]['price_per_person'] is None and found[0]['availability'] == 'unknown'
    from backend.streams.C_discovery.local_catalog import merge_sources
    assert len(merge_sources(found, [{'source_url': found[0]['source_url'] + '/booking'}])) == 1


def test_bar_cards_reach_api_without_web_and_never_sell_a_pint_as_a_date(client, monkeypatch, tmp_path):
    _, member, _ = ready(client)
    ImportedCatalog(client.app.state.v2['db']).import_bundle(bundle(tmp_path, [bar(i) for i in range(1, 5)]))
    def no_web(*a, **kw): raise AssertionError('Local bar request must not call provider')
    monkeypatch.setattr(client.app.state.v2['planning'].web, 'search', no_web)
    response = client.post('/api/v2/dates/search', headers=headers(member), json={
        'constraints': {'text': 'bar terrasse', 'categories': ['nightlife'], 'mode': 'offline', 'activity_count': 1}})
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data['activities']) == 4 and not data['proposals']
    card = data['activities'][0]
    assert card['pint_price_from_eur'] == 5 and card['offer_note']
    assert card['price_per_person'] is None and not card['composable'] and card['checked_at'] is None
    assert card['address'].startswith('42 Rue') and card['source_name'] == 'mistergoodbeer'
