"""Persistent internal demo catalog and explainable, consent-scoped discovery.

Fairness = .60 * min(A, B) + .40 * mean(A, B). Hard constraints are
applied before ranking; history, distance and category diversity are penalties.
Only the memory service's consent-filtered planning context enters this layer.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timedelta, timezone

from backend.streams.E_orchestrator.models import CandidateActivity, TimeWindow


def _now():
    return datetime.now(timezone.utc).isoformat()


def _normal(value):
    return re.sub(r"[^\w]+", " ", str(value).casefold()).strip()


def _matches(terms, value):
    value={'loud spaces':'loud','crowds':'social'}.get(str(value).casefold(),value)
    return bool(_normal(value)) and f" {_normal(value)} " in f" {terms} "


def _list(value):
    if isinstance(value, list):
        return value
    return [value] if isinstance(value, str) else []


def _distance(location, origin):
    lat1, lat2 = map(math.radians, (location['lat'], origin['lat']))
    dlat = lat2-lat1
    dlng = math.radians(origin['lng']-location['lng'])
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlng/2)**2
    return 6371 * 2 * math.asin(min(1, math.sqrt(a)))


def demo_catalog():
    """Fictional experiences, never represented as verified businesses."""
    categories = [
        ('food', 'Seasonal tasting table', 24, ['vegetarian', 'vegan', 'intimate'], True),
        ('culture', 'Small gallery wander', 10, ['art', 'calm', 'quiet'], True),
        ('concerts', 'Acoustic listening session', 18, ['music', 'social', 'loud'], True),
        ('cinema', 'Independent film evening', 12, ['film', 'calm', 'quiet'], True),
        ('outdoors', 'Riverside discovery walk', 0, ['nature', 'walking', 'calm'], False),
        ('sport', 'Playful movement workshop', 16, ['active', 'energetic'], True),
        ('workshops', 'Clay and colour studio', 28, ['creative', 'art', 'intimate'], True),
        ('nightlife', 'Rooftop music hour', 20, ['music', 'social', 'loud'], False),
        ('home', 'At-home recipe adventure', 8, ['vegetarian', 'vegan', 'intimate', 'quiet'], True),
        ('travel', 'Neighbourhood mini escape', 14, ['walking', 'nature', 'novel'], False),
    ]
    slots = [('10:00', '11:00'), ('15:00', '16:00'), ('19:00', '20:00'), ('21:00', '22:00')]
    neighborhoods = ['Canal', 'Rive gauche', 'Marais', 'Bastille']
    rows = []
    for i, (category, title, price, tags, indoor) in enumerate(categories):
        for j, (start, end) in enumerate(slots):
            rows.append({
                'id': f'demo_{category}_{j+1}', 'title': f'{title} · {neighborhoods[j]}',
                'description': 'Fictional internal demo experience for exploring Chandelle. No real venue or availability is claimed.',
                'category': category, 'subcategory': tags[0], 'tags': tags,
                'price_per_person': price + j * 2 if price else 0, 'currency': 'EUR',
                'duration_minutes': 60, 'location': {'lat': 48.855+i*.001, 'lng': 2.342+j*.002},
                'address': 'Illustrative Paris location; no real venue', 'neighborhood': neighborhoods[j],
                'indoor': indoor, 'weather_sensitive': not indoor,
                'accessibility': {'wheelchair': category not in ['sport', 'travel'], 'step_free': category not in ['sport', 'travel'], 'quiet': 'quiet' in tags, 'seating': category not in ['sport','travel','outdoors']},
                'weekdays': list(range(7)), 'start': start, 'end': end,
                'opening_windows': [{'start': start, 'end': end}], 'available': True,
                'availability_source': 'internal_demo_unverified', 'last_verified_at': None,
                'booking_url': None, 'media': [], 'popularity': .5, 'rating': None,
                'source': 'Chandelle fictional internal catalog', 'provider': 'internal', 'demo': True,
                'hard_constraints': [], 'embedding_metadata': None,
            })
    return rows


class CatalogService:
    def __init__(self, db, memory):
        self.db, self.memory = db, memory

    def seed(self):
        rows = demo_catalog()
        with self.db.connect() as con:
            con.executemany('INSERT OR IGNORE INTO v2_activities(id,payload) VALUES (?,?)',
                            [(row['id'], json.dumps(row)) for row in rows])
        return len(rows)

    def browse(self, query='', category=None, limit=30, offset=0):
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError('limit must be 1–100 and offset must be nonnegative')
        with self.db.connect() as con:
            rows = [json.loads(row['payload']) for row in con.execute('SELECT payload FROM v2_activities ORDER BY id')]
        words = _normal(query).split()
        rows = [row for row in rows if (not category or row['category'] == category)
                and all(_matches(_normal(' '.join([row['title'], row['description'], row['category'], *row['tags']])), word) for word in words)]
        return {'items': rows[offset:offset+limit], 'total': len(rows), 'limit': limit, 'offset': offset}

    def get(self, activity_id):
        with self.db.connect() as con:
            row = con.execute('SELECT payload FROM v2_activities WHERE id=?', (activity_id,)).fetchone()
        if not row:
            raise KeyError(activity_id)
        return json.loads(row['payload'])

    def set_state(self, user_id, activity_id, state):
        if state not in {'saved', 'liked', 'disliked', 'rejected', 'neutral'}:
            raise ValueError('Unknown activity state')
        self.get(activity_id)
        with self.db.connect() as con:
            con.execute('INSERT INTO v2_activity_states(user_id,activity_id,state,updated_at) VALUES (?,?,?,?) '
                        'ON CONFLICT(user_id,activity_id) DO UPDATE SET state=excluded.state,updated_at=excluded.updated_at',
                        (user_id, activity_id, state, _now()))
        return {'activity_id': activity_id, 'state': state}

    def discover(self, couple_id, time_window, budget=None, categories=None, radius_km=None, limit=30, query=''):
        window = TimeWindow.model_validate(time_window) if isinstance(time_window, dict) else time_window
        if limit < 1 or limit > 100 or (budget is not None and budget < 0) or (radius_km is not None and radius_km < 0):
            raise ValueError('Invalid discovery limit, budget or radius')
        context = self.memory.planning_context(couple_id)
        profiles = [context.get('person_a', {}), context.get('person_b', {}), context.get('couple', {})]
        budgets = [budget] if budget is not None else []
        for profile in profiles:
            value = profile.get('budget')
            if isinstance(value, dict) and not value.get('flexible') and value.get('max') is not None:
                budgets.append(float(value['max']) * (2 if value.get('unit', 'person') == 'person' else 1))
            elif isinstance(value, (float, int)):
                budgets.append(float(value))
        cap = min(budgets) if budgets else None
        with self.db.connect() as con:
            members = [row['user_id'] for row in con.execute('SELECT user_id FROM v2_memberships WHERE couple_id=? ORDER BY role', (couple_id,))]
            states = {uid: {row['activity_id']: row['state'] for row in con.execute('SELECT activity_id,state FROM v2_activity_states WHERE user_id=?', (uid,))} for uid in members}
            history = [json.loads(row['payload']) for row in con.execute("SELECT payload FROM v2_plans WHERE couple_id=? AND status='completed'", (couple_id,))]
            catalog = [json.loads(row['payload']) for row in con.execute('SELECT payload FROM v2_activities ORDER BY id')]
        seen = {activity['id'] for plan in history for activity in plan.get('activities', [])}
        origin = profiles[2].get('location') or {'lat': 48.8566, 'lng': 2.3522}
        rows = []
        for activity in catalog:
            terms = _normal(' '.join([activity['title'], activity['category'], *activity['tags']]))
            start = datetime.combine(window.start.date(), datetime.strptime(activity['start'], '%H:%M').time(), window.start.tzinfo)
            if start < window.start and window.end.date() > window.start.date():
                start += timedelta(days=1)
            end = start + timedelta(minutes=activity['duration_minutes'])
            distance = _distance(activity['location'], origin)
            if (not activity.get('available', True) or start < window.start or end > window.end or start.weekday() not in activity['weekdays']
                    or (cap is not None and activity['price_per_person']*2 > cap)
                    or (categories and activity['category'] not in categories)
                    or (radius_km is not None and distance > radius_km)
                    or any(state.get(activity['id']) in {'disliked', 'rejected'} for state in states.values())):
                continue
            excluded = False
            for profile in profiles:
                constraints = profile.get('constraints') or {}
                if not isinstance(constraints, dict):
                    constraints = {}
                dislikes = _list(profile.get('dislikes'))
                days = constraints.get('days') or []
                names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                day_allowed = not days or start.weekday() in days or names[start.weekday()] in [str(x).lower() for x in days]
                if (any(_matches(terms, value) for value in dislikes) or not day_allowed
                        or any(not activity['accessibility'].get(value, False) for value in _list(constraints.get('accessibility')))
                        or (activity['category'] in {'food', 'home'} and any(not _matches(terms, value) for value in _list(constraints.get('dietary'))))
                        or (constraints.get('travel_minutes') is not None and distance / 4 * 60 > float(constraints['travel_minutes']))):
                    excluded = True
            if excluded:
                continue
            scores = []
            for index, profile in enumerate(profiles[:2]):
                interests = _list(profile.get('interests'))
                matches = sum(_matches(terms, value) for value in interests)
                state = states.get(members[index], {}).get(activity['id']) if index < len(members) else None
                scores.append(min(1, .45 + min(.4, matches*.2) + (.1 if state in {'saved', 'liked'} else 0)))
            fairness = .6*min(scores) + .4*sum(scores)/2
            novelty = float(profiles[2].get('novelty', .5) or 0)
            novelty_penalty = .2*novelty if activity['id'] in seen else 0
            distance_penalty = min(.15, distance*.015)
            shared_bonus = .05 if any(_matches(terms, value) for value in _list(profiles[2].get('interests'))) else 0
            query_bonus = .08 if query and any(_matches(terms, value) for value in _normal(query).split()) else 0
            score = max(0, min(1, fairness + shared_bonus + query_bonus - novelty_penalty - distance_penalty))
            candidate = CandidateActivity(id=activity['id'], type=activity['category'], name=activity['title'],
                start=activity['start'], end=activity['end'], price_per_person=activity['price_per_person'],
                location=activity['location'], tags=activity['tags'], booking_url=activity['booking_url'],
                match_score=score, user_a_score=scores[0], user_b_score=scores[1])
            rows.append({'activity': activity, 'candidate': candidate.model_dump(mode='json'),
                         'person_a_score': scores[0], 'person_b_score': scores[1], 'couple_score': score,
                         'components': {'fairness': fairness, 'shared_bonus': shared_bonus, 'query_bonus': query_bonus,
                                        'novelty_penalty': novelty_penalty, 'distance_penalty': distance_penalty, 'distance_km': round(distance, 2), 'diversity_penalty': 0},
                         'evidence': ['Consent-filtered preferences from both member profiles and the couple profile.',
                                      f"Fictional internal catalog; {activity['price_per_person']*2:g} EUR for two; {activity['duration_minutes']} minutes.",
                                      'Previous completed experience reduces novelty.' if novelty_penalty else 'No completed occurrence in local history.']})
        selected, counts = [], {}
        while rows and len(selected) < limit:
            rows.sort(key=lambda row: (-(row['couple_score'] - .035*counts.get(row['activity']['category'], 0)), row['activity']['id']))
            row = rows.pop(0)
            category = row['activity']['category']
            penalty = .035*counts.get(category, 0)
            row['components']['diversity_penalty'] = penalty
            row['couple_score'] = round(max(0, row['couple_score']-penalty), 6)
            row['candidate']['match_score'] = row['couple_score']
            selected.append(row)
            counts[category] = counts.get(category, 0)+1
        return selected
