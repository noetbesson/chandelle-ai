"""Small bilingual offline vocabulary, adapted from peer signals/domain modules."""


import re
import unicodedata
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, Field
from backend.db import now
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




class Conversation(BaseModel):
    text: str=Field(min_length=1,max_length=4000)
    privacy_scope: Privacy='PRIVATE'
    mode: Literal['offline','openai']='offline'


class ConversationService:
    def __init__(self, db, memory):
        self.db, self.memory = db, memory

    def ingest(self, member, body, adapter):
        extraction=adapter.extract(body.text,member['id'])
        sid=uuid4().hex
        with self.db.connect() as c:
            c.execute('INSERT INTO v2_conversations VALUES(?,?,?,?)',(sid,member['couple_id'],member['id'],now()))
            c.execute('INSERT INTO v2_messages VALUES(?,?,?,?,?)',(uuid4().hex,sid,member['id'],body.text,now()))
        facts=[self.memory.ingest(member['couple_id'],'PERSON',member['id'],member['id'],f.category,'conversation:'+sid+':'+str(i),{'values':[f.value]},body.privacy_scope,'conversation') for i,f in enumerate(extraction.facts)]
        return {'conversation_id':sid,'facts':facts,'mode':adapter.last_mode}
