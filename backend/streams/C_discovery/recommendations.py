"""Real-source recommendations, independent of calendars and fictional catalogs.

A future database plugs into ActivitySource.activities(), using the existing Activity
contract. Missing facts stay unknown; only complete, dated events reach E.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Protocol
import re
import json
from zoneinfo import ZoneInfo
from pydantic import ValidationError
from backend.integrations.urls import public_url
from backend.streams.C_discovery.normalizers.models import Activity
from backend.streams.C_discovery.service import _distance
from backend.streams.H_conversation.service import interests, normalize
from backend.streams.E_orchestrator.models import CandidateActivity
from backend.streams.C_discovery.locations import matches_location, paris_district

PARIS = ZoneInfo('Europe/Paris')
ALIASES = {'restaurant':'food','dinner':'food','concert':'concerts','museum':'culture',
           'exhibition':'culture','exposition':'culture','expo/performance':'culture',
           'walk':'outdoors','bar':'nightlife','atelier':'workshops'}

class ActivitySource(Protocol):
    def activities(self) -> list[dict]: ...

class SourcedActivity(Activity):
    # Imported public sources retain their actual provenance, never an AI label.
    source: str
    attribution: str


class DatabaseActivities:
    def __init__(self, db):
        self.db = db

    def search(self, intent):
        from backend.streams.C_discovery.local_catalog import ImportedCatalog
        query = ' '.join([intent.summary, *intent.preferences])
        imported = ImportedCatalog(self.db).search(query, intent.categories, limit=200, location=intent.location)
        with self.db.connect() as c:
            web = [json.loads(row[0]) for row in c.execute(
                "SELECT payload FROM v2_activities WHERE json_extract(payload,'$.provider')='openai_web'")]
        return [self.adapt(row) for row in [*imported, *web]]

    @staticmethod
    def adapt(row):
        location = row.get('location') or {}
        dated = row.get('kind') in ('event', 'screening', 'bookable_slot') and row.get('schedule_status') == 'published'
        return {'id': row['id'], 'kind': 'event' if dated else 'place',
            'type': row['category'], 'name': row['title'], 'description': row.get('description') or None,
            'tags': row.get('tags', []), 'start': row.get('starts_at') if dated else None, 'end': row.get('ends_at') if dated else None,
            'opening_hours': None, 'price_per_person': row.get('price_per_person'),
            'price_level': row.get('price_tier'),
            'location': {'lat': location.get('lat'), 'lng': location.get('lng'),
                         'address': row.get('address') or row.get('city') or None,
                         'arrondissement': paris_district(row.get('address') or '')},
            'booking_url': row.get('booking_url'), 'website': row.get('source_url') or row.get('source'),
            'image_url': row.get('image_url'), 'rating': row.get('rating'),
            'source': row.get('source_name') or row.get('provider') or 'public_source',
            'attribution': row.get('source_name') or 'Recherche web',
            'match_score': None, 'why': None, 'fetched_at': row.get('checked_at')}


def terms(text):
    normalized = normalize(text)
    return set(re.findall(r'\w+', normalized)) | set(interests(text)[0])


def matches(text, values):
    words = terms(text)
    return any(terms(value) <= words for value in values if terms(value))


def effective_budget(context, explicit):
    caps = [explicit] if explicit is not None else []
    for profile in context.values():
        value = profile.get('budget')
        if isinstance(value, (int, float)):
            caps.append(value)
        elif isinstance(value, dict) and not value.get('flexible') and value.get('max') is not None:
            caps.append(value['max'] * (2 if value.get('unit', 'person') == 'person' else 1))
    return min(caps) if caps else None


class RealRecommendations:
    def __init__(self, db, memory, source=None):
        self.db, self.memory = db, memory
        self.source = source or DatabaseActivities(db)

    def search(self, cid, intent, limit=4, extra_records=()):
        context = self.memory.planning_context(cid)
        budget = effective_budget(context, intent.budget)
        profiles = [context['person_a'], context['person_b'], context['couple']]
        with self.db.connect() as c:
            disliked = {r[0] for r in c.execute("SELECT activity_id FROM v2_activity_states WHERE user_id IN (SELECT user_id FROM v2_memberships WHERE couple_id=?) AND state IN ('disliked','rejected')", (cid,))}
        records = self.source.search(intent) if hasattr(self.source, 'search') else self.source.activities()
        records = [*extra_records, *records]
        rows, rejected = [], {'expired':0, 'constraints':0, 'invalid':0}
        seen=set()
        now = datetime.now(timezone.utc)
        for raw in records:
            try:
                a = SourcedActivity.model_validate(raw)
                if a.id in seen:
                    continue
                if not a.website or not public_url(str(a.website)):
                    raise ValueError('No public source')
            except (ValidationError, ValueError, TypeError):
                rejected['invalid'] += 1
                continue
            seen.add(a.id)
            # An event with no end cannot be promised as still ongoing after its start.
            if a.kind == 'event' and (a.end or a.start) and (a.end or a.start) < now:
                rejected['expired'] += 1
                continue
            text = ' '.join([a.name, a.type, a.description or '', *a.tags])
            category = ALIASES.get(normalize(a.type), normalize(a.type))
            if category not in ('food','culture','concerts','cinema','outdoors','sport','workshops','nightlife','home','travel'):
                inferred = interests(text)[0]
                category = next((x for x in inferred if x in ('culture','food','concerts','outdoors','cinema','workshops')), category)
            searchable = text + ' ' + category
            excluded = [*intent.excluded, *[v for p in profiles for v in p.get('dislikes', [])]]
            location_ok = matches_location(intent.location, a.location.address, a.location.arrondissement)
            known_date_conflict = False
            if intent.date_from and a.kind=='event' and a.start:
                day_start=date.fromisoformat(intent.date_from)
                day_end=date.fromisoformat(intent.date_to or intent.date_from)
                known_date_conflict=(a.end or a.start).astimezone(PARIS).date()<day_start or a.start.astimezone(PARIS).date()>day_end
            if intent.start and intent.end and a.kind == 'event' and a.start and a.end:
                left, right = datetime.fromisoformat(intent.start), datetime.fromisoformat(intent.end)
                known_date_conflict = known_date_conflict or a.end <= left or a.start >= right
            if (a.id in disliked or a.id in intent.avoid_ids or matches(searchable, excluded)
                or (intent.categories and category not in intent.categories)
                or (budget is not None and a.price_per_person is not None and a.price_per_person*2 > budget)
                or not location_ok
                or known_date_conflict):
                rejected['constraints'] += 1
                continue
            unknown = ['Disponibilité à confirmer auprès du lieu']
            if a.fetched_at is None or a.fetched_at.utcoffset() is None or (now-a.fetched_at).total_seconds()>7*86400: unknown.append('Source ancienne ou non datée : détails à revérifier')
            if a.price_per_person is None: unknown.append('Prix inconnu')
            if not a.start or not a.end: unknown.append('Horaire ou durée à confirmer')
            elif (a.end-a.start).total_seconds()>8*3600: unknown.append('Période d’événement : créneau de visite à préciser')
            if a.location.lat is None or a.location.lng is None: unknown.append('Coordonnées manquantes pour calculer les trajets')
            constraints = [p.get('constraints') or {} for p in profiles]
            # Do not infer accessibility or a dietary guarantee from an unrelated tag.
            if any(c.get('accessibility') or c.get('dietary') for c in constraints):
                unknown.append('Accessibilité / régime alimentaire à vérifier')
            requested = sum(matches(searchable, [v]) for v in intent.preferences)
            scores = [min(1, .45 + .2*sum(matches(searchable, [v]) for v in p.get('interests', []))) for p in profiles[:2]]
            query_bonus=min(.3,.1*requested)
            score = .6*min(scores) + .4*sum(scores)/2 + query_bonus
            evidence = []
            if intent.categories: evidence.append('Catégorie demandée')
            if requested: evidence.append('Correspond à ' + ', '.join(v for v in intent.preferences if matches(searchable, [v])))
            if budget is not None and a.price_per_person is not None: evidence.append('Prix indiqué compatible avec le budget à deux')
            if not evidence: evidence.append('Piste issue du catalogue réel ; détails à vérifier sur la source')
            item = a.model_dump(mode='json')
            item.update(category=category, score=round(score, 4), query_bonus=query_bonus, person_a_score=scores[0], person_b_score=scores[1],
                        reasons=evidence, unknown=unknown, demo=False,
                        total_couple_cost=None if a.price_per_person is None else a.price_per_person*2)
            rows.append(item)
        rows.sort(key=lambda a: (a['price_per_person'] is None if budget is not None else False, -a['score'], a['id']))
        unique = {}
        for item in rows:
            key = (normalize(item['name']), item['location']['arrondissement']) if item['kind']=='place' else item['id']
            unique.setdefault(key, item)
        rows = list(unique.values())
        return {'items':rows[:limit], 'total':len(rows), 'rejected':rejected,
                'source_count':len(records), 'budget_cap':budget,
                'status':'found' if rows else 'no_matching_real_activity'}

    def candidates(self, cid, intent, window, budget):
        # Re-filter on every plan request so stale sessions cannot bypass revoked consent.
        candidates = []
        context = self.memory.planning_context(cid)
        for item in self.search(cid, intent, limit=100)['items']:
            if intent.selected_ids and item['id'] not in intent.selected_ids:
                continue
            a = Activity.model_validate({k:v for k,v in item.items() if k in Activity.model_fields})
            if (a.kind != 'event' or not a.start or not a.end or a.price_per_person is None
                or a.location.lat is None or a.location.lng is None):
                continue
            start, end = a.start.astimezone(PARIS), a.end.astimezone(PARIS)
            # Multi-week exhibitions describe an opening period, not a visit/session.
            if not 0 < (end-start).total_seconds() <= 8*3600 or start < window.start or end > window.end:
                continue
            represented=datetime.combine(window.start.date(),start.time(),window.start.tzinfo)
            if window.end.date()>window.start.date() and represented<window.start:
                represented+=timedelta(days=1)
            if represented!=start:continue  # E's HH:MM contract must preserve the actual event date.
            if a.price_per_person*2 > budget:
                continue
            blocked = False
            for p in context.values():
                c = p.get('constraints') or {}
                days = c.get('days') or []
                if days and start.weekday() not in days and start.strftime('%A').lower() not in [str(d).lower() for d in days]: blocked = True
                # The shared Activity contract lacks verified accessibility/diet fields.
                if c.get('accessibility') or c.get('dietary'): blocked = True
                if c.get('travel_minutes') is not None:
                    origin = context['couple'].get('location')
                    if not origin or _distance(a.location.model_dump(), origin)/4*60 > c['travel_minutes']: blocked = True
            if blocked:
                continue
            candidate = CandidateActivity(id=a.id, type=item['category'], name=a.name,
                start=start.strftime('%H:%M'), end=end.strftime('%H:%M'), price_per_person=a.price_per_person,
                location={'lat':a.location.lat,'lng':a.location.lng}, match_score=min(1,item['score']),
                tags=a.tags, booking_url=str(a.booking_url) if a.booking_url and public_url(str(a.booking_url)) else None,
                user_a_score=min(1,item['person_a_score']+item['query_bonus']),
                user_b_score=min(1,item['person_b_score']+item['query_bonus']))
            candidates.append({'activity':{**item,'title':a.name,'source':str(a.website),'address':a.location.address or '',
                                          'description':a.description or '', 'demo':False},
                'candidate':candidate.model_dump(mode='json'), 'person_a_score':item['person_a_score'],
                'person_b_score':item['person_b_score'], 'couple_score':min(1,item['score']),
                'evidence':[*item['reasons'], 'Horaires issus de la source ; places et prix à reconfirmer.']})
        return candidates
