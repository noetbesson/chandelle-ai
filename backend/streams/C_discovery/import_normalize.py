"""Read supplied exports only. Never fetch a page, execute a formula or infer a price.

openpyxl is needed by the import command only; the application reads the compact bundle.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
import hashlib
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

from backend.integrations.urls import public_url

FILES = ('allocine.xlsx', 'Café.xlsx', 'Cheap restaurant.xlsx', 'Dessert.xlsx',
         'Medium priced restaurant.xlsx', 'Resto chic.xlsx', 'Sortir à paris.xlsx', 'Bar.xlsx')
MONTHS = {v: i for i, v in enumerate(('janvier', 'fevrier', 'mars', 'avril', 'mai', 'juin',
                                    'juillet', 'aout', 'septembre', 'octobre', 'novembre', 'decembre'), 1)}
CUISINES = {'japanese': 'japonais', 'italian': 'italien', 'french': 'francais',
            'chinese': 'chinois', 'indian': 'indien', 'asian': 'asiatique', 'thai': 'thailandais',
            'korean': 'coreen', 'vietnamese': 'vietnamien', 'mediterranean': 'mediterraneen',
            'lebanese': 'libanais', 'mexican': 'mexicain', 'vegetarian': 'vegetarien',
            'vegan': 'vegetalien', 'seafood': 'fruits de mer', 'pizza': 'pizza',
            'sushi': 'sushi', 'barbecue': 'grillades', 'steakhouse': 'viande'}


def text(value: object) -> str:
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def fold(value: object) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', text(value).casefold()) if not unicodedata.combining(c))


def french_date(value: str) -> str | None:
    match = re.fullmatch(r'(\d{1,2})(?:er)? (' + '|'.join(MONTHS) + r') (20\d{2})', fold(value))
    if match:
        try:
            return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()
        except ValueError:
            pass
    return None


def advertised_dates(value: str) -> tuple[str | None, str | None]:
    """Only explicit, unambiguous date/range with a year; never resolve 'demain'.

    Dates remain article claims, not verified showtimes. Multiple ranges stay unknown.
    """
    value = fold(value)
    month = '(' + '|'.join(MONTHS) + ')'
    ranges = re.findall(r'\bdu (\d{1,2})(?:er)?(?: ' + month + r')? au (\d{1,2})(?:er)? ' + month + r' (20\d{2})', value)
    if ranges:
        dates = {(french_date(f'{a} {ma or mb} {year}'), french_date(f'{b} {mb} {year}')) for a, ma, b, mb, year in ranges}
        if len(dates) == 1:
            start, end = next(iter(dates))
            if start and end and start <= end:
                return start, end
        return None, None
    dates = {french_date(' '.join(m)) for m in re.findall(r'\b(\d{1,2})(?:er)? ' + month + r' (20\d{2})', value)} - {None}
    if len(dates) == 1:
        result = next(iter(dates))
        return result, result
    return None, None


def number(value: object, maximum: float) -> float | None:
    try:
        result = float(text(value).replace(',', '.'))
        return result if 0 <= result <= maximum else None
    except ValueError:
        return None


def record(row: dict, filename: str, sheet: str, row_number: int) -> dict | None:
    source = ('mistergoodbeer' if 'BarGrid_barName__ggBLd' in row else
              'tripadvisor' if 'biGQs' in row else 'allocine' if 'meta-title-link' in row else 'sortiraparis')
    url_key, title_key = {'tripadvisor': ('BMQDV href', 'biGQs'),
                          'allocine': ('meta-title-link href', 'meta-title-link'),
                          'sortiraparis': ('col-xs-12 href', 'col-xs-12 2'),
                          'mistergoodbeer': ('BarGrid_cardLink__NF2Km href', 'BarGrid_barName__ggBLd')}[source]
    url = public_url(text(row.get(url_key)))
    title = re.sub(r'^\d+\.\s+', '', text(row.get(title_key)))
    if not url or not title:
        return None
    host = urlsplit(url).hostname or ''
    hosts = {'tripadvisor': {'tripadvisor.com', 'tripadvisor.fr'}, 'allocine': {'allocine.fr'},
             'sortiraparis': {'sortiraparis.com'}, 'mistergoodbeer': {'mistergoodbeer.com'}}
    if host not in hosts[source]:
        return None
    pattern = {'tripadvisor': r'-d(\d+)-', 'allocine': r'cfilm=(\d+)', 'sortiraparis': r'/articles/(\d+)',
               'mistergoodbeer': r'/bars/([a-z0-9-]+)(?:/|$|[?#])'}[source]
    match = re.search(pattern, url)
    if not match:
        return None
    ident = source + ':' + match[1]
    result = {'id': ident, 'source_name': source, 'source_id': match[1], 'source_url': url,
              'title': title, 'kind': 'place', 'category': 'food', 'tags': [],
              'department': None, 'city': None, 'price_tier': None, 'rating': None,
              'review_count': None, 'description': '', 'start_date': None, 'end_date': None,
              'source_observed_at': None, 'last_verified_at': None,
              'eligibility': 'needs_location', 'provenance': [[filename, sheet, row_number]]}
    if source == 'tripadvisor':
        # g187147 is the explicit Paris place ID in the supplied URLs, not the file's name.
        if '-g187147-' in url and '-Paris_Ile_de_France' in url:
            result.update(department='75', city='Paris', eligibility='candidate')
        raw_tags = text(row.get('biGQs 4'))
        tags = [fold(t) for t in raw_tags.split(',') if text(t)]
        tags += [translated for en, translated in CUISINES.items() if en in tags]
        if filename == 'Café.xlsx':
            tags += ['cafe', 'coffee', 'tea']
        elif filename == 'Dessert.xlsx':
            tags += ['dessert', 'patisserie']
        else:
            tags += ['restaurant']
        result['tags'] = sorted(set(tags))
        tier = text(row.get('biGQs 5'))
        result['price_tier'] = {'$': 'budget', '$$ - $$$': 'moderate', '$$$$': 'upscale'}.get(tier)
        result['rating'] = number(row.get('biGQs 2'), 5)
        reviews = re.fullmatch(r'\(([\d,\s]+) reviews?\)', text(row.get('biGQs 3')))
        if reviews:
            result['review_count'] = int(re.sub(r'\D', '', reviews[1]))
        if re.search(r'permanently closed|definitivement ferme', fold(row.get('biGQs 6'))):
            result['eligibility'] = 'closed'
        # Discard Open now / Closed now: no observation date or actual opening hours.
    elif source == 'mistergoodbeer':
        address = text(row.get('BarGrid_address__a3r3v'))
        postal = re.search(r'\b(75|77|78|91|92|93|94|95)\d{3}\s+([^,]+)', address)
        tags = [fold(row.get('BarTags_tag_design__gliEq' + suffix)) for suffix in ('', ' 2', ' 3')]
        pint_claims = [m[1] for tag in tags if (m := re.fullmatch(r'pinte a partir de (\d+(?:[.,]\d+)?)\s*€', tag))]
        prices = {number(v, 100) for v in pint_claims} - {None}
        result.update(category='nightlife', address=address,
                      tags=sorted({'bar', *(t for t in tags if t and not t.startswith('pinte a partir de '))}),
                      rating=number(row.get('BarGrid_ratingSummary__Km40k'), 5),
                      pint_price_from_eur=next(iter(prices)) if len(prices) == 1 else None,
                      offer_note=text(row.get('BarGrid_dealText__MxiVc')) or None)
        if postal:
            result.update(department=postal[1], city=postal[2].strip(), eligibility='candidate')
        reviews = re.fullmatch(r'\(([\d\s]+) avis\)', text(row.get('BarGrid_ratingCount__TVP0T')))
        if reviews:
            result['review_count'] = int(re.sub(r'\D', '', reviews[1]))
        # The export's badge, 'verified' claim and reservable capacity prove neither
        # an observation date, an available slot nor a per-person outing budget.
    elif source == 'allocine':
        cells = list(row.items())
        tags = [text(cells[i-1][1]) for i, (k, v) in enumerate(cells)
                if i and 'href' in k and '/films/genre-' in text(v)]
        result.update(kind='film', category='cinema', eligibility='reference', tags=sorted(set(filter(None, tags))),
                      description=text(row.get('content-txt')), release_date=french_date(text(row.get('date'))),
                      rating=number(row.get('stareval-note 2'), 5),
                      director=text(row.get('xXx 2')) or None,
                      showtimes_url=public_url(text(row.get('button href'))))
        duration = re.search(r'(\d+)h\s*(\d+)min', text(row.get('meta-body-item')))
        result['film_duration_minutes'] = int(duration[1]) * 60 + int(duration[2]) if duration else None
    else:
        description = text(row.get('col-xs-12'))
        content = fold(title + ' ' + description)
        category = next((cat for key, cat in (('/concert-musique/', 'concerts'), ('/spectacle/', 'culture'),
                        ('/theatre/', 'culture'), ('/balades/', 'outdoors'), ('/sport/', 'sport'),
                        ('/exposition/', 'culture'), ('/cinema/', 'cinema'), ('/gastronomie/', 'food')) if key in url), 'culture')
        result.update(kind='article', category=category, description=description,
                      tags=[fold(sheet)], eligibility='needs_location')
        # Strong named location evidence only. A publisher called Sortiraparis is not geographic evidence.
        for name, dept in (('seine saint denis', '93'), ('hauts de seine', '92'), ('val de marne', '94'),
                           ('seine et marne', '77'), ('val d oise', '95'), ('yvelines', '78'), ('essonne', '91'),
                           ('paris', '75'), ('parisien', '75'), ('parisienne', '75')):
            if re.search(r'\b' + name + r'\b', re.sub(r'[-’\']', ' ', content)):
                result.update(department=dept, city='Paris' if dept == '75' else None, eligibility='candidate')
                break
        result['start_date'], result['end_date'] = advertised_dates(description)
        # Editorial news/broadcasts/reviews are useful references, not outings.
        if re.search(r'\b(qui est|mtv|grammy|chaine|livestream|televise|streaming|ephemeride|resultats|bande annonce|netflix|prime video)\b', content):
            result['eligibility'] = 'reference'
        if re.search(r'\b(annule|annulee)\b', fold(title)):
            result['eligibility'] = 'cancelled'
    return result


def normalize_directory(folder: Path) -> tuple[list[dict], dict]:
    import openpyxl
    records: dict[str, dict] = {}
    summary = {'files': [], 'valid_source_rows': 0, 'duplicate_rows': 0, 'ignored_nondata_rows': 0, 'conflicts': 0}
    for filename in FILES:
        path = folder / filename
        if filename == 'Bar.xlsx' and not path.is_file():
            continue  # Existing seven-workbook imports remain supported.
        # Fail on a missing input before publishing a partial bundle.
        if not path.is_file():
            raise FileNotFoundError(filename)
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        stats = {'file': filename, 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'rows': 0}
        try:
            for sheet in workbook:
                header = None
                for rownum, values in enumerate(sheet.values, 1):
                    if any(v in ('BMQDV href', 'meta-title-link', 'col-xs-12 href', 'BarGrid_cardLink__NF2Km href') for v in values):
                        header = [text(v) for v in values]
                        continue
                    if not header or not any(v not in (None, '') for v in values):
                        continue
                    value = record(dict(zip(header, values)), filename, sheet.title, rownum)
                    if not value:
                        summary['ignored_nondata_rows'] += 1
                        continue
                    stats['rows'] += 1
                    summary['valid_source_rows'] += 1
                    previous = records.get(value['id'])
                    if previous:
                        summary['duplicate_rows'] += 1
                        previous['provenance'] += value['provenance']
                        previous['tags'] = sorted(set(previous['tags'] + value['tags']))
                        for field in ('price_tier', 'rating', 'review_count', 'pint_price_from_eur', 'offer_note'):
                            if field not in previous and field not in value:
                                continue
                            if previous.get(field) is not None and value.get(field) is not None and previous[field] != value[field]:
                                summary['conflicts'] += 1
                                previous.setdefault('conflicting_fields', {})[field] = sorted(set(previous.get('conflicting_fields', {}).get(field, []) + [previous[field], value[field]]), key=str)
                                previous[field] = None
                            elif previous.get(field) is None and field not in previous.get('conflicting_fields', {}):
                                previous[field] = value.get(field)
                        if value['eligibility'] in ('closed', 'cancelled'):
                            previous['eligibility'] = value['eligibility']
                    else:
                        records[value['id']] = value
        finally:
            workbook.close()
        summary['files'].append(stats)
    values = sorted(records.values(), key=lambda v: v['id'])
    summary.update(unique_records=len(values), by_source=dict(Counter(v['source_name'] for v in values)),
                   by_eligibility=dict(Counter(v['eligibility'] for v in values)),
                   source_bytes=sum(v['bytes'] for v in summary['files']))
    return values, summary
