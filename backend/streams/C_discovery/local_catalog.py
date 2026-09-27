"""Indexed imported sources in the application's existing SQLite database.

The gzip file is a portable data release, not another database. FTS indexes the
existing v2_activities rows. Unknown prices, hours and verification stay unknown.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import gzip
import hashlib
import json
import re
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit

from backend.integrations.urls import public_url
from backend.streams.C_discovery.import_normalize import fold, CUISINES

BUNDLE = Path(__file__).with_name('data') / 'imported_catalog.jsonl.gz'
IDF = {'75', '77', '78', '91', '92', '93', '94', '95'}
STOP = set('un une le la les de des du d l et puis ensuite avec pour dans a au aux en je nous on tu il elle voudrais veux souhaite cherche trouver propose sortie sorties activite activites ce cette ces soir demain aujourd hui weekend week end prochain prochaine paris ile france budget moins plus euros euro eur autour pres restaurant restaurants repas diner manger balade cafe cafes cinema film films concert concerts expo exposition moi vous quelque chose faire aimerais ai envie bon bonne bons idees pouvez peux nous'.split())


def is_active(value: dict) -> bool:
    if value.get('eligibility') != 'candidate' or value.get('department') not in IDF:
        return False
    today = datetime.now(ZoneInfo('Europe/Paris')).date().isoformat()
    return not value.get('end_date') or value['end_date'] >= today


def activity_record(value: dict, imported_at: str) -> dict:
    """Compatible public activity; imports never fabricate an E candidate."""
    return {**value, 'name': value['title'], 'provider': 'user_import', 'demo': False,
            'price': None, 'price_per_person': None, 'price_unit': 'unknown', 'currency': 'EUR',
            'address': value.get('address', ''), 'location': None, 'start': None, 'end': None, 'starts_at': None,
            'ends_at': None, 'duration_minutes': None, 'schedule_status': 'unknown',
            'availability': 'unknown', 'checked_at': None, 'last_verified_at': None,
            'imported_at': imported_at, 'source': value['source_url'], 'booking_url': None,
            'accessibility': {}, 'media': [], 'popularity': None}


class ImportedCatalog:
    def __init__(self, db):
        self.db = db

    def import_bundle(self, path: Path = BUNDLE) -> dict:
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        with self.db.connect() as c:
            old = c.execute('SELECT summary FROM v2_catalog_imports WHERE bundle=? AND digest=?',
                            (path.name, digest)).fetchone()
        if old:
            return {**json.loads(old[0]), 'unchanged': True}
        # Validate the full release first; any error preserves the previous catalogue.
        records = [json.loads(line) for line in gzip.decompress(raw).decode('utf-8').splitlines() if line]
        ids = set()
        for value in records:
            if (value['id'] in ids or value['source_name'] not in ('tripadvisor', 'allocine', 'sortiraparis', 'mistergoodbeer')
                or value['id'] != value['source_name'] + ':' + value['source_id']
                or not public_url(value['source_url']) or not value['title']
                or value['kind'] not in ('place', 'film', 'article')):
                raise ValueError('Invalid imported source record')
            ids.add(value['id'])
        now = datetime.now(timezone.utc).isoformat()
        stats = {'bundle': path.name, 'digest': digest, 'records': len(records), 'inserted': 0,
                 'updated': 0, 'unchanged_records': 0, 'imported_at': now, 'unchanged': False}
        with self.db.atomic():
            with self.db.connect() as c:
                for value in records:
                    old = c.execute('SELECT payload FROM v2_activities WHERE id=?', (value['id'],)).fetchone()
                    previous = json.loads(old[0]) if old else None
                    row = activity_record(value, previous.get('imported_at', now) if previous else now)
                    encoded = json.dumps(row, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
                    stats['unchanged_records' if previous == row else 'updated' if old else 'inserted'] += 1
                    if previous != row:
                        c.execute('INSERT INTO v2_activities VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload', (row['id'], encoded))
                    c.execute('DELETE FROM v2_activity_search WHERE id=?', (row['id'],))
                    c.execute('INSERT INTO v2_activity_search(id,title,tags,description) VALUES(?,?,?,?)',
                              (row['id'], fold(row['title']), fold(' '.join(row['tags'])), fold(row['description'])))
                # An input's disappearance is not evidence of closure: keep earlier records.
                c.execute('INSERT INTO v2_catalog_imports VALUES(?,?,?,?) ON CONFLICT(bundle) DO UPDATE SET '
                          'digest=excluded.digest,summary=excluded.summary,imported_at=excluded.imported_at',
                          (path.name, digest, json.dumps(stats), now))
        return stats

    def status(self) -> dict:
        with self.db.connect() as c:
            rows = [json.loads(r[0]) for r in c.execute("SELECT payload FROM v2_activities WHERE json_extract(payload,'$.provider')='user_import'")]
        return {'records': len(rows), 'searchable': sum(is_active(r) for r in rows),
                'sources': dict(Counter(r['source_name'] for r in rows))}

    def search(self, query: str, categories=(), limit: int = 80, *, references: bool = False) -> list[dict]:
        """FTS tokenizer receives quoted words only, never raw user search syntax."""
        normalized = fold(query)
        tier = next((tier for pattern, tier in ((r'pas cher|economique|petit budget', 'budget'),
                    (r'haut de gamme|gastronomique|chic', 'upscale'), (r'prix moyen|gamme intermediaire', 'moderate'))
                     if re.search(pattern, normalized)), None)
        lexical = re.sub(r'pas cher|economique|petit budget|haut de gamme|gastronomique|chic|prix moyen|gamme intermediaire', '', normalized)
        tokens = [t for t in re.findall(r'[a-z0-9]+', lexical) if len(t) > 1 and t not in STOP and not t.isdigit()]
        tokens = list(dict.fromkeys(tokens))[:20]
        if 'nightlife' in categories and len(tokens) > 1:
            tokens = [t for t in tokens if t not in ('bar', 'bars')]
        # Explicit cafe/dessert intent distinguishes these from the food category.
        for needle, term in ((r'\bcafes?\b|coffee', 'cafe'), (r'dessert|patisserie|gateau', 'dessert')):
            if re.search(needle, normalized) and term not in tokens:
                tokens.append(term)
        for en, fr in CUISINES.items():
            if en in tokens and fr not in tokens:
                tokens.append(fr)
            elif fr in tokens and en not in tokens:
                tokens.append(en)
        match = ' OR '.join('"' + t + '"' for t in tokens)
        args: list = []
        if match:
            sql = 'SELECT a.payload,bm25(v2_activity_search,0,8,5,1) AS relevance FROM v2_activity_search JOIN v2_activities a ON a.id=v2_activity_search.id WHERE v2_activity_search MATCH ?'
            args.append(match)
        else:
            sql = "SELECT payload,0 AS relevance FROM v2_activities WHERE json_extract(payload,'$.provider')='user_import'"
        if categories:
            sql += ' AND json_extract(payload,\'$.category\') IN (' + ','.join('?' for _ in categories) + ')'
            args.extend(categories)
        if tier:
            sql += " AND json_extract(payload,'$.price_tier')=?"
            args.append(tier)
        if 'nightlife' in categories and re.search(r'\bterrasse\b', normalized) and not re.search(r'\b(sans|pas de) terrasse\b', normalized):
            # A 'Pas de terrasse' tag must not match a request for a terrace.
            sql += " AND EXISTS (SELECT 1 FROM json_each(json_extract(payload,'$.tags')) WHERE value IN ('petite terrasse','grande terrasse','terrasse'))"
        if not references:
            sql += " AND json_extract(payload,'$.eligibility')='candidate' AND (json_extract(payload,'$.end_date') IS NULL OR json_extract(payload,'$.end_date')>=?)"
            args.append(datetime.now(ZoneInfo('Europe/Paris')).date().isoformat())
        sql += " ORDER BY relevance,json_extract(payload,'$.id') LIMIT ?"
        args.append(min(max(limit, 1), 200))
        with self.db.connect() as c:
            found = [json.loads(r[0]) for r in c.execute(sql, args)]
        return [{**r, '_query_rank': i} for i, r in enumerate(found) if references or is_active(r)]

    def shortlist(self, rows: list[dict], limit: int = 8) -> list[dict]:
        # A handful of public references, no full workbook or personal memory in the prompt.
        return [{'name': a['title'], 'category': a['category'], 'source_url': a['source_url'],
                 'kind': a['kind']} for a in rows[:limit]]


def merge_sources(local: list[dict], web: list[dict]) -> list[dict]:
    """Prefer newly checked web facts for the same source identity, without guessing by name."""
    def identity(row):
        url = public_url(row['source_url']) or ''
        host = urlsplit(url).hostname
        provider, pattern = {'tripadvisor.com': ('tripadvisor', r'-d(\d+)-'),
                             'tripadvisor.fr': ('tripadvisor', r'-d(\d+)-'),
                             'allocine.fr': ('allocine', r'cfilm=(\d+)'),
                             'sortiraparis.com': ('sortiraparis', r'/articles/(\d+)'),
                             'mistergoodbeer.com': ('mistergoodbeer', r'/bars/([a-z0-9-]+)(?:/|$|[?#])')}.get(host, ('', 'a^'))
        match = re.search(pattern, url)
        return provider + ':' + match[1] if match else url
    fresh_urls = {identity(r) for r in web}
    # Keep web duplicates until the shared deduplication stage, so its trace remains
    # meaningful. Imported source rows themselves stay pristine in the database.
    return [r for r in local if identity(r) not in fresh_urls] + web
