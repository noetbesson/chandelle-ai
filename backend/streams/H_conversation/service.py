"""Small bilingual offline vocabulary, adapted from peer signals/domain modules."""


import re
import hashlib
import unicodedata
from typing import Literal
from types import SimpleNamespace
from uuid import uuid4
from pydantic import BaseModel, Field
from backend.db import now, encoded
import hashlib
import json
from backend.streams.B_memory.service import Privacy


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD',str(text)) if not unicodedata.combining(c)).lower().replace('’',"'")


VOCABULARY = {
    'japanese':r'japonais\w*|sushi\w*|ramen\w*|japanese',
    'jazz':r'jazz', 'workshops':r'atelier\w*|workshops?',
    'creative':r'creati\w*|ceramiqu\w*|poteri\w*|peinture\w*',
    'outdoors':r'balade\w*|promenad\w*|outdoors?',
    'nature':r'nature|foret\w*|parc\w*|jardin\w*',
    'cinema':r'cinema\w*|film\w*', 'culture':r'culture\w*|musee\w*|exposition\w*|expo|theatre\w*',
    'concerts':r'concert\w*', 'music':r'musiqu\w*|music',
    'sport':r'sport\w*|escalade|yoga|tennis|velo',
    'quiet':r'calme\w*|tranquill\w*|quiet',
    'vegetarian':r'vegetarien\w*|vegetarian', 'vegan':r'vegan\w*',
    'italian':r'italien\w*|pizza\w*|italian',
    'food':r'restaurant\w*|resto\w*|diner|food|dinner',
    'nightlife':r'bars?|cocktails?|nightlife',
    'home':r'domicile|maison|home', 'travel':r'escapade\w*|travel',
}


def interests(text):
    """Propose likes only; negated imports never create hard exclusions."""
    positive, negative=set(),set()
    for clause in re.split(r'[.!?;\n]|\bmais\b|\bbut\b',normalize(re.sub(r'https?://\S+','',text))):
        for tag,pattern in VOCABULARY.items():
            for match in re.finditer(r'\b(?:'+pattern+r')\b',clause):
                before=clause[:match.start()]
                neg=list(re.finditer(r"\b(?:pas|jamais|sans|eviter|evite|deteste|refuse|aucun|ni|no|avoid|hate|dislike)\b",before))
                pos=list(re.finditer(r"\b(?:j'aime|j'adore|je veux|je prefere|love|enjoy|like)\b",before))
                after=clause[match.end():]
                excluded=(neg[-1].start() if neg else -1)>(pos[-1].start() if pos else -1) or bool(re.match(r'\s*(?:non merci|a eviter)',after))
                (negative if excluded else positive).add(tag)
    return sorted(positive-negative),sorted(negative)


def parse_request(text):
    s=normalize(text)
    amount=re.search(r'(\d+(?:[.,]\d+)?)\s*(?:€|euros?\b|eur\b)',s)
    if not amount:amount=re.search(r'(?:under|below|budget|moins de|max(?:imum)?)\s*(?:de|of)?\s*€?\s*(\d+(?:[.,]\d+)?)',s)
    budget=float(amount[1].replace(',','.')) if amount else None
    if budget is not None and re.search(r'chacun|par personne|/\s*pers|each|per person',s):budget*=2
    likes,excluded=interests(text)
    cats={'food','culture','concerts','cinema','outdoors','sport','workshops','nightlife','home','travel'}
    return {'budget':budget,'categories':[v for v in likes if v in cats],'excluded':excluded}




TEMPORAL = r"\b(ce soir|aujourd'hui|demain|cette semaine|tonight|today|tomorrow)\b"


def durable_preferences(text):
    """Conservative local extraction: first-person assertions, no questions/quotes.

    This intentionally does not turn every mention or request into a lasting taste.
    """
    results = []
    pattern = re.compile(
        r"^(?:i\s+(?P<en>love|like|enjoy|hate|dislike|avoid|don't like|do not like)|"
        r"j['’](?P<fr>aime|adore)|je\s+(?P<fr2>déteste|deteste|préfère|prefere)|"
        r"je\s+n['’]aime\s+(?P<neg>pas|plus)|(?P<want>je veux|j['’]ai envie de|i want))\s+(?P<value>.+)$", re.I)
    for clause in re.split(r'[.!;\n]|\bmais\b|\bbut\b', text):
        clause = clause.strip()
        if '?' in clause:
            continue
        match = pattern.match(clause)
        if not match:
            continue
        verb = normalize(next(v for v in (match['en'], match['fr'], match['fr2'], match['neg'], match['want']) if v))
        negative = verb in {'hate', 'dislike', 'avoid', "don't like", 'do not like', 'deteste', 'pas', 'plus'}
        temporary = bool(match['want'] or re.search(TEMPORAL, clause, re.I))
        raw_value = re.sub(TEMPORAL, '', match['value'], flags=re.I).strip()
        value = re.sub(r'^(?:(?:le|la|les|du|des|de la)\s+|l[’\'])', '', raw_value, flags=re.I).strip()
        # Negated or attributed clauses need language understanding; do not guess.
        if re.search(r"\b(pas|plus|not|because|parce que|dit|says)\b", value, re.I):
            continue
        if value:
            results.append({'category': 'dislikes' if negative else 'interests',
                            'value': value[:500], 'confidence': .85,
                            'horizon': 'temporary' if temporary else 'durable'})
    return results


class Conversation(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    privacy_scope: Privacy = 'PRIVATE'
    mode: Literal['offline', 'openai'] = 'offline'
    conversation_id: str | None = Field(default=None, max_length=100)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=100)
    horizon: Literal['durable', 'temporary'] = 'durable'
    learn: bool = True
    auto_share: bool = True


class ConversationService:
    def __init__(self, db, memory):
        self.db, self.memory = db, memory

    def _authorize(self, member, sid):
        with self.db.connect() as c:
            row = c.execute('SELECT id FROM v2_conversations WHERE id=? AND user_id=? AND couple_id=?',
                            (sid, member['id'], member['couple_id'])).fetchone()
        if row is None:
            raise PermissionError('Unknown personal conversation')

    def history(self, member, sid):
        self._authorize(member, sid)
        with self.db.connect() as c:
            messages = [dict(r) for r in c.execute(
                'SELECT id,content,created_at FROM v2_messages WHERE conversation_id=? AND user_id=? ORDER BY created_at,id',
                (sid, member['id']))]
        return {'conversation_id': sid, 'messages': messages}

    def list(self, member, limit=100, offset=0):
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError('Invalid journal pagination')
        with self.db.connect() as c:
            return {'items': [dict(r) for r in c.execute(
                'SELECT id,created_at FROM v2_conversations WHERE user_id=? AND couple_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?',
                (member['id'], member['couple_id'], limit, offset))], 'limit': limit, 'offset': offset,
                'total': c.execute('SELECT count(*) FROM v2_conversations WHERE user_id=? AND couple_id=?',
                                   (member['id'], member['couple_id'])).fetchone()[0]}

    def _replay(self, member, key, fingerprint):
        if not key:
            return None
        with self.db.connect() as c:
            previous = c.execute('SELECT * FROM v2_memory_interactions WHERE user_id=? AND request_key=?',
                                 (member['id'], key)).fetchone()
        if previous is None:
            return None
        if previous['fingerprint'] != fingerprint:
            raise ValueError('Idempotency key already used for a different interaction')
        # Re-read current authorized state: replay cannot resurrect deleted facts.
        active = self.memory.list_facts(member['couple_id'], 'PERSON', member['id'], member['id'])
        ids = set(json.loads(previous['fact_ids']))
        return {'conversation_id': previous['conversation_id'], 'interaction_id': previous['id'],
                'facts': [f for f in active if f['id'] in ids], 'mode': previous['mode'], 'replayed': True}

    def ingest(self, member, body, adapter):
        self.memory._member(member['couple_id'], member['id'])
        if body.conversation_id:
            self._authorize(member, body.conversation_id)
        if not body.text.strip():
            raise ValueError('Message cannot be empty')
        fingerprint = hashlib.sha256(encoded({**body.model_dump(exclude={'idempotency_key'}), 'explicit_privacy': 'privacy_scope' in body.model_fields_set}).encode()).hexdigest()
        replay = self._replay(member, body.idempotency_key, fingerprint)
        if replay is not None:
            return replay
        # Provider work happens before the write transaction and only by opt-in.
        candidates = []
        if body.learn:
            extraction = adapter.extract(body.text, member['id'])
            if adapter.last_mode == 'offline':
                candidates = [SimpleNamespace(**f) for f in durable_preferences(body.text)]
            else:
                candidates = [SimpleNamespace(**f.model_dump(), horizon='temporary' if re.search(TEMPORAL, body.text, re.I) else body.horizon) for f in extraction.facts]
        sid, iid, mid = body.conversation_id or uuid4().hex, uuid4().hex, uuid4().hex
        with self.db.atomic():
            replay = self._replay(member, body.idempotency_key, fingerprint)
            if replay is not None:
                return replay
            if body.conversation_id:
                self._authorize(member, sid)
            with self.db.connect() as c:
                if not body.conversation_id:
                    c.execute('INSERT INTO v2_conversations VALUES(?,?,?,?)', (sid, member['couple_id'], member['id'], now()))
                c.execute('INSERT INTO v2_messages VALUES(?,?,?,?,?)', (mid, sid, member['id'], body.text, now()))
            facts = self.memory.learn(member['couple_id'], member['id'], candidates,
                                      body.privacy_scope, iid, body.horizon,
                                      auto_share=body.auto_share and 'privacy_scope' not in body.model_fields_set)
            with self.db.connect() as c:
                c.execute('INSERT INTO v2_memory_interactions VALUES(?,?,?,?,?,?,?,?)',
                    (iid, member['id'], sid, mid, body.idempotency_key, fingerprint,
                     encoded([f['id'] for f in facts]), adapter.last_mode))
        return {'conversation_id': sid, 'interaction_id': iid, 'facts': facts,
                'mode': adapter.last_mode, 'replayed': False}
