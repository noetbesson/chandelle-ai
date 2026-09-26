"""Native, consent-aware V2 memory. SQL facts are authoritative; vectors are optional.

No Mem0 implementation is bundled. ``MemoryBackend`` documents the adapter boundary.
Private person retrieval is owner-only, independently of caller-provided entity IDs.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol, Literal
from backend.db import now, encoded as dump

Privacy = Literal["PRIVATE", "COUPLE_RECOMMENDATION", "SHARED"]


SCOPES = {"PERSON", "COUPLE", "SESSION", "DATE"}
VISIBILITIES = {"PRIVATE", "COUPLE_RECOMMENDATION", "SHARED"}
# Exact allowlist: free text, health, diet, religion, budgets and relationships
# cannot be classified as safe by a model and automatically disclosed.
AUTO_SHARE_PREFERENCES = {
    'jazz': 'jazz', 'cinéma': 'cinema', 'cinema': 'cinema', 'movies': 'cinema',
    'musées': 'museums', 'museums': 'museums', 'culture': 'culture',
    'concerts': 'concerts', 'nature': 'nature', 'balades': 'outdoors',
    'walks': 'outdoors', 'outdoors': 'outdoors', 'poterie': 'creative',
    'pottery': 'creative', 'peinture': 'creative', 'painting': 'creative',
    'ateliers': 'workshops', 'workshops': 'workshops',
}
PUBLIC_CATEGORIES = {"food", "culture", "concerts", "cinema", "outdoors", "sport", "workshops", "nightlife", "home", "home dates", "travel"}


def terms(value: Any) -> set[str]:
    return set(re.findall(r"[\w]+", str(value).casefold()))


class SemanticBackend(Protocol):
    provider: str
    model: str
    def embed(self, text: str) -> list[float]: ...


class LocalSemanticBackend:
    """Stable token hashing; useful offline similarity, not a language model."""
    provider = "local"
    model = "token-hash-64-v1"

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * 64
        for token in terms(text):
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:2], "big") % 64] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class MemoryBackend(Protocol):
    """Optional Mem0-compatible adapters must preserve these authorization rules."""
    def ingest(self, couple_id: str, scope: str, entity_id: str, owner_id: str,
               category: str, key: str, value: Any, **kwargs: Any) -> dict: ...
    def search(self, couple_id: str, scope: str, entity_id: str, viewer_id: str,
               query: str, limit: int = 20) -> list[dict]: ...
    def delete_entity(self, couple_id: str, scope: str, entity_id: str, viewer_id: str) -> dict: ...


class SQLiteMemoryRepository:
    """Small repository boundary: authorization stays in the service."""
    def __init__(self, db):
        self.db = db

    def active(self, couple_id: str, scope: str, entity_id: str) -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM v2_facts WHERE couple_id=? AND scope=? AND entity_id=? AND deleted=0 AND (valid_to IS NULL OR valid_to>?) ORDER BY created_at,id", (couple_id, scope, entity_id, now())).fetchall()
        return [decode(row) for row in rows]

    def get(self, fact_id: str) -> dict:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM v2_facts WHERE id=?", (fact_id,)).fetchone()
        if not row or row["deleted"]:
            raise KeyError("Memory not found")
        return decode(row)


def decode(row) -> dict:
    result = dict(row)
    result["value"] = json.loads(result["value"])
    result["tags"] = json.loads(result["tags"] or "[]")
    return result


class MemoryServiceV2:
    def __init__(self, db, semantic: SemanticBackend | None = None):
        self.db = db
        self.repository = SQLiteMemoryRepository(db)
        self.semantic = semantic or LocalSemanticBackend()

    def _member(self, couple_id: str, viewer_id: str) -> dict:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM v2_memberships WHERE couple_id=? AND user_id=?", (couple_id, viewer_id)).fetchone()
        if not row:
            raise PermissionError("Member does not belong to this couple")
        return dict(row)

    def _scope(self, couple_id: str, scope: str, entity_id: str, owner_id: str):
        if scope not in SCOPES or not entity_id or not owner_id:
            raise ValueError("Invalid memory scope")
        self._member(couple_id, owner_id)
        if scope == "PERSON" and entity_id != owner_id:
            raise PermissionError("Person memories belong only to their owner")
        if scope == "COUPLE" and entity_id != couple_id:
            raise ValueError("Couple memory entity must match couple")

    def _event(self, conn, fact: dict, kind: str, payload: Any, idempotency_key=None):
        conn.execute("INSERT INTO v2_events(id,couple_id,entity_id,fact_id,kind,payload,source,created_at,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?)", (uuid.uuid4().hex, fact["couple_id"], fact["entity_id"], fact["id"], kind, dump(payload), fact["source"], now(), idempotency_key))

    def ingest(self, couple_id: str, scope: str, entity_id: str, owner_id: str,
               category: str, key: str, value: Any, privacy_scope: str = "PRIVATE",
               source: str = "manual", tags: list[str] | None = None,
               idempotency_key: str | None = None, supersedes: str | None = None,
               confidence: float = 1.0, salience: float = 0.5,
               entities: list[str] | None = None) -> dict:
        self._scope(couple_id, scope, entity_id, owner_id)
        if privacy_scope not in VISIBILITIES:
            raise ValueError("Invalid privacy scope")
        if scope == "COUPLE" and privacy_scope != "SHARED":
            raise ValueError("Couple facts must be explicitly shared")
        if not isinstance(category, str) or not category.strip() or not isinstance(key, str) or not key.strip():
            raise ValueError("Category and key must not be empty")
        if not 0 <= confidence <= 1 or not 0 <= salience <= 1:
            raise ValueError("Confidence and salience must be between zero and one")
        if tags is not None and (not isinstance(tags, list) or any(not isinstance(t, str) for t in tags)):
            raise ValueError("Tags must be strings")
        encoded = dump(value)
        event_key = None
        if idempotency_key:
            event_key = dump([couple_id, scope, entity_id, owner_id, key, idempotency_key])
        moment = now()
        active = self.repository.active(couple_id, scope, entity_id)
        if supersedes:
            old = self.repository.get(supersedes)
            if any(old[field] != expected for field, expected in (("couple_id", couple_id), ("scope", scope), ("entity_id", entity_id), ("owner_id", owner_id))):
                raise PermissionError("Cannot supersede another entity's memory")
        else:
            old = None
        fact = {"id": uuid.uuid4().hex, "couple_id": couple_id, "scope": scope,
                "entity_id": entity_id, "owner_id": owner_id, "category": category,
                "key": key, "value": value, "tags": tags or [], "privacy_scope": privacy_scope,
                "consent_state": "private" if privacy_scope == "PRIVATE" else "granted",
                "confidence": confidence, "salience": salience, "valid_from": moment,
                "valid_to": None, "created_at": moment, "updated_at": moment,
                "last_accessed_at": None, "reinforcement_count": 1,
                "supersedes": supersedes, "contradicted_by": None, "source": source, "deleted": 0}
        with self.db.connect() as conn:
            if event_key:
                previous = conn.execute("SELECT fact_id FROM v2_events WHERE idempotency_key=?", (event_key,)).fetchone()
                if previous:
                    return self.repository.get(previous["fact_id"])
            duplicate = next((f for f in active if f["owner_id"] == owner_id and f["key"] == key and f["category"] == category and dump(f["value"]) == encoded and f["privacy_scope"] == privacy_scope and not f["contradicted_by"]), None)
            if duplicate and not supersedes:
                conn.execute("UPDATE v2_facts SET reinforcement_count=reinforcement_count+1,updated_at=? WHERE id=?", (moment, duplicate["id"]))
                self._event(conn, duplicate, "reinforced", {"value": value, "privacy_scope": privacy_scope}, event_key)
                fact = duplicate
            else:
                columns = list(fact)
                persisted = {**fact, "value": encoded, "tags": dump(fact["tags"])}
                conn.execute(f"INSERT INTO v2_facts ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", tuple(persisted[column] for column in columns))
                if old:
                    conn.execute("UPDATE v2_facts SET valid_to=?,updated_at=? WHERE id=?", (moment, moment, old["id"]))
                    self._event(conn, old, "superseded", {"by": fact["id"]})
                else:
                    conflicting = [f for f in active if f["owner_id"] == owner_id and f["category"] == category and f["key"] == key and dump(f["value"]) != encoded]
                    for conflict in conflicting:
                        conn.execute("UPDATE v2_facts SET contradicted_by=?,updated_at=? WHERE id=?", (fact["id"], moment, conflict["id"]))
                        self._event(conn, conflict, "conflict", {"by": fact["id"]})
                self._event(conn, fact, "created", {"value": value, "privacy_scope": privacy_scope, "supersedes": supersedes}, event_key)
                conn.execute("INSERT INTO v2_entities(id,couple_id,kind,label) VALUES(?,?,?,?) ON CONFLICT(id) DO NOTHING", (entity_id, couple_id, scope, entity_id))
                conn.execute("INSERT OR IGNORE INTO v2_links(fact_id,entity_id) VALUES(?,?)", (fact["id"], entity_id))
                for linked in entities or []:
                    # Caller supplies labels; entity identity is namespaced to the couple.
                    linked_id = hashlib.sha256((couple_id + ':' + linked).encode()).hexdigest()
                    conn.execute("INSERT INTO v2_entities(id,couple_id,kind,label) VALUES(?,?,?,?) ON CONFLICT(id) DO NOTHING", (linked_id, couple_id, "TAG", linked))
                    conn.execute("INSERT OR IGNORE INTO v2_links(fact_id,entity_id) VALUES(?,?)", (fact["id"], linked_id))
                # Only locally computed vectors are stored automatically. Remote providers
                # require an explicit caller invocation; ingest never opens a socket.
                local = LocalSemanticBackend()
                vector = local.embed(category + ' ' + key + ' ' + encoded + ' ' + ' '.join(tags or []))
                conn.execute("INSERT OR REPLACE INTO v2_embeddings(fact_id,provider,model,vector,updated_at) VALUES(?,?,?,?,?)", (fact["id"], local.provider, local.model, dump(vector), moment))
                self._index(conn, fact)
        self.derive_couple(couple_id)
        return self.repository.get(fact["id"])

    def _index(self, conn, fact):
        # FTS is an optional accelerator; absence or missing SQLite extension is fine.
        import sqlite3
        try:
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS v2_memory_fts USING fts5(fact_id UNINDEXED,content)")
            conn.execute("DELETE FROM v2_memory_fts WHERE fact_id=?", (fact["id"],))
            conn.execute("INSERT INTO v2_memory_fts(fact_id,content) VALUES(?,?)", (fact["id"], fact["category"] + ' ' + fact["key"] + ' ' + dump(fact["value"]) + ' ' + ' '.join(fact["tags"])))
        except sqlite3.OperationalError:
            pass

    def list_facts(self, couple_id: str, scope: str, entity_id: str, viewer_id: str) -> list[dict]:
        self._member(couple_id, viewer_id)
        if scope not in SCOPES:
            raise ValueError("Invalid memory scope")
        if scope == "PERSON" and entity_id != viewer_id:
            raise PermissionError("Only the owner can open a person memory")
        if scope == "COUPLE" and entity_id != couple_id:
            raise PermissionError("Invalid couple scope")
        facts = self.repository.active(couple_id, scope, entity_id)
        if scope == "COUPLE":
            shared = [f for f in facts if f["privacy_scope"] == "SHARED" and f["consent_state"] == "granted"]
            for member in self._members(couple_id):
                shared.extend(f for f in self._allowed(couple_id, member["user_id"]) if f["privacy_scope"] == "SHARED")
            return shared
        return [f for f in facts if f["owner_id"] == viewer_id]

    def search(self, couple_id: str, scope: str, entity_id: str, viewer_id: str,
               query: str, limit: int = 20) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")
        facts = self.list_facts(couple_id, scope, entity_id, viewer_id)
        query_terms = terms(query)
        # Deterministic embedding is always the default. Optional provider interfaces
        # can be supplied by integration code after explicit consent checks.
        vector = self.semantic.embed(query)
        fts_ids = set()
        import sqlite3
        with self.db.connect() as conn:
            if query_terms:
                try:
                    expression = ' OR '.join('"' + token.replace('"', '""') + '"' for token in sorted(query_terms))
                    fts_ids = {r["fact_id"] for r in conn.execute("SELECT fact_id FROM v2_memory_fts WHERE v2_memory_fts MATCH ?", (expression,)).fetchall()}
                except sqlite3.OperationalError:
                    pass
            for fact in facts:
                content = fact["category"] + ' ' + fact["key"] + ' ' + dump(fact["value"]) + ' ' + ' '.join(fact["tags"])
                lexical = len(query_terms & terms(content)) / max(1, len(query_terms))
                if fact["id"] in fts_ids:
                    lexical = min(1.0, lexical + 0.1)
                stored = conn.execute("SELECT vector,provider,model FROM v2_embeddings WHERE fact_id=?", (fact["id"],)).fetchone()
                semantic = 0.0
                if stored and stored["provider"] == self.semantic.provider and stored["model"] == self.semantic.model:
                    other = json.loads(stored["vector"])
                    if len(vector) == len(other):
                        denom = math.sqrt(sum(v*v for v in vector) * sum(v*v for v in other)) or 1.0
                        semantic = max(0.0, sum(a*b for a,b in zip(vector,other)) / denom)
                linked = conn.execute("SELECT e.label FROM v2_links l JOIN v2_entities e ON e.id=l.entity_id WHERE l.fact_id=?", (fact["id"],)).fetchall()
                labels = set(fact["tags"])
                for row in linked:
                    labels.update(terms(row["label"]))
                entity_overlap = len(query_terms & {x.casefold() for x in labels}) / max(1, len(query_terms))
                age_days = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(fact["updated_at"])).total_seconds() / 86400)
                recency = math.exp(-age_days/180)
                reinforcement = min(1.0, math.log1p(fact["reinforcement_count"])/math.log(11))
                signals = {"lexical": lexical, "semantic": semantic, "entity_overlap": entity_overlap,
                           "recency": recency, "confidence": fact["confidence"], "salience": fact["salience"],
                           "reinforcement": reinforcement, "decay": recency}
                score = .35*lexical + .20*semantic + .10*entity_overlap + .10*recency + .10*fact["confidence"] + .10*fact["salience"] + .05*reinforcement*recency
                fact["retrieval_score"] = round(score, 6)
                fact["retrieval_signals"] = signals
            facts.sort(key=lambda f: (-f["retrieval_score"], f["id"]))
            chosen = facts[:limit]
            for fact in chosen:
                conn.execute("UPDATE v2_facts SET last_accessed_at=? WHERE id=?", (now(), fact["id"]))
        return chosen

    def _owned(self, fact_id: str, viewer_id: str) -> dict:
        fact = self.repository.get(fact_id)
        self._member(fact["couple_id"], viewer_id)
        if fact["owner_id"] != viewer_id:
            raise PermissionError("Only the memory owner can change it")
        return fact

    def update(self, fact_id: str, viewer_id: str, **changes) -> dict:
        old = self._owned(fact_id, viewer_id)
        allowed = {"value", "category", "key", "tags", "privacy_scope", "confidence", "salience"}
        if set(changes) - allowed:
            raise ValueError("Unsupported memory field")
        fields = {k: old[k] for k in ("couple_id", "scope", "entity_id", "owner_id", "category", "key", "value", "privacy_scope", "tags", "confidence", "salience")}
        fields.update(changes)
        return self.ingest(**fields, supersedes=fact_id, source=old["source"] if old["source"]=="inspiration_import" else "correction")

    def delete(self, fact_id: str, viewer_id: str) -> dict:
        fact = self._owned(fact_id, viewer_id)
        with self.db.connect() as conn:
            conn.execute("UPDATE v2_facts SET deleted=1,valid_to=?,updated_at=? WHERE id=?", (now(), now(), fact_id))
            conn.execute("DELETE FROM v2_embeddings WHERE fact_id=?", (fact_id,))
            self._event(conn, fact, "deleted", {"by": viewer_id})
            self._remove_index(conn, [fact_id])
        self.derive_couple(fact["couple_id"])
        return {"id": fact_id, "deleted": True}

    def _remove_index(self, conn, ids):
        import sqlite3
        try:
            conn.executemany("DELETE FROM v2_memory_fts WHERE fact_id=?", [(item,) for item in ids])
        except sqlite3.OperationalError:
            pass

    def share(self, fact_id: str, viewer_id: str, privacy_scope: str = "SHARED") -> dict:
        fact = self._owned(fact_id, viewer_id)
        if privacy_scope not in VISIBILITIES:
            raise ValueError("Invalid privacy scope")
        if fact["scope"] == "COUPLE" and privacy_scope != "SHARED":
            # A couple-scoped fact cannot become a private fact while remaining there.
            # Revoke removes its shared visibility; the provenance remains owner-only.
            self.delete(fact_id, viewer_id)
            return {"id": fact_id, "deleted": True, "privacy_scope": privacy_scope}
        with self.db.connect() as conn:
            conn.execute("UPDATE v2_facts SET privacy_scope=?,consent_state=?,updated_at=? WHERE id=?", (privacy_scope, "private" if privacy_scope == "PRIVATE" else "granted", now(), fact_id))
            self._event(conn, fact, "consent_changed", {"from": fact["privacy_scope"], "to": privacy_scope})
        self.derive_couple(fact["couple_id"])
        return self.repository.get(fact_id)

    def revoke(self, fact_id: str, viewer_id: str) -> dict:
        return self.share(fact_id, viewer_id, "PRIVATE")

    def provenance(self, fact_id: str, viewer_id: str) -> list[dict]:
        fact = self.repository.get(fact_id)
        self._member(fact["couple_id"], viewer_id)
        if fact["owner_id"] != viewer_id:
            raise PermissionError("Only the owner may export raw provenance")
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM v2_events WHERE fact_id=? ORDER BY created_at,id", (fact_id,)).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]

    def _build_profile(self, entity_id: str, scope: str, facts: list[dict], internal=False) -> dict:
        profile = {"entity_id": entity_id, "scope": scope, "interests": [], "dislikes": [],
                   "budget": {}, "novelty": .5, "style": {}, "constraints": {"days": [], "dietary": [], "accessibility": []},
                   "recent_patterns": [], "unresolved_conflicts": [], "provenance_summary": {}, "fact_count": len(facts)}
        interests, dislikes = set(), set()
        weights = {}
        for fact in facts:
            value = fact["value"]
            weight = 1.0
            if fact['source']=='inspiration_import' and isinstance(value,dict):
                if not value.get('confirmed'):continue
                if value.get('horizon')=='temporary':
                    stamp=value.get('signal_at')
                    try:
                        age=int(max(0,(datetime.now(timezone.utc)-datetime.fromisoformat(stamp)).total_seconds()/86400)) if stamp else None
                    except (ValueError,TypeError):age=None
                    if age is not None and age>=45:continue
                    weight=math.exp(-age/30) if age is not None else .1
            category = fact["category"].casefold()
            key = fact["key"].casefold()
            label = category + ' ' + key
            profile["provenance_summary"][fact["source"]] = profile["provenance_summary"].get(fact["source"], 0) + 1
            if fact["contradicted_by"]:
                if not internal:
                    profile["unresolved_conflicts"].append({"fact_id": fact["id"], "contradicted_by": fact["contradicted_by"], "category": fact["category"]})
                # Contradictory assertions remain retrievable but newer assertion wins
                # structured projection; the owner can explicitly supersede either.
                continue
            values = value.get("values", []) if isinstance(value, dict) else value if isinstance(value, list) else [value] if isinstance(value, str) else []
            if not isinstance(values, list):
                values = []
            clean = [v.strip().casefold() for v in values if isinstance(v,str) and v.strip()]
            if any(word in label for word in ("dislike", "avoid", "no_go")):
                dislikes.update(clean)
            elif any(word in label for word in ("interest", "favorite", "repeat", "liked", "like")):
                interests.update(clean)
                for tag in clean:weights[tag]=max(weights.get(tag,0),weight)
            if "budget" in label and isinstance(value, dict):
                budget = {k: value[k] for k in ("min", "max") if isinstance(value.get(k), (int,float)) and not isinstance(value.get(k), bool) and value[k] >= 0}
                budget["unit"] = value.get("unit") if value.get("unit") in {"person", "couple"} else "person"
                budget["flexible"] = value.get("flexible") is True
                profile["budget"] = budget
            elif "budget" in label and isinstance(value, (int, float)) and not isinstance(value, bool):
                profile["budget"] = {"max": value, "unit": "person"}
            if "style" in label and isinstance(value, dict):
                profile["style"] = {k: float(v) for k,v in value.items() if k in {"energy", "social", "novelty", "outdoor", "duration"} and isinstance(v,(float,int)) and 0 <= v <= 1}
                profile["novelty"] = profile["style"].get("novelty", .5)
            if "novelty" in label and isinstance(value,(float,int)) and 0 <= value <= 1:
                profile["novelty"] = value
            if any(word in label for word in ("practical", "constraint")) and isinstance(value,dict):
                for k in ("days", "dietary", "accessibility"):
                    if isinstance(value.get(k), list):
                        profile["constraints"][k] = [v for v in value[k] if isinstance(v, str)]
                for k in ("travel_minutes", "radius_km"):
                    if isinstance(value.get(k), (int,float)) and not isinstance(value.get(k), bool) and value[k] >= 0:
                        profile["constraints"][k] = value[k]
            if category in {"feedback", "history", "date"} and not internal:
                profile["recent_patterns"].append({"category": category, "source": fact["source"], "recorded_at": fact["created_at"]})
        # Durable conversational corrections override the corresponding interview
        # selection, without editing its original answer or losing provenance.
        for fact in sorted(facts, key=lambda f: (f['updated_at'], f['id'])):
            if scope != 'PERSON' or not fact['key'].startswith('learned:durable:preference:') or fact['contradicted_by']:
                continue
            value = fact['value']
            for tag in value.get('values', []) if isinstance(value, dict) else []:
                if not isinstance(tag, str):
                    continue
                tag = tag.strip().casefold()
                if fact['category'] == 'dislikes':
                    interests.discard(tag)
                    dislikes.add(tag)
                elif fact['category'] == 'interests':
                    dislikes.discard(tag)
                    interests.add(tag)
                    weights[tag] = 1.0
        profile["interest_weights"] = {k:v for k,v in weights.items() if k not in dislikes}
        profile["interests"] = sorted(interests - dislikes)
        profile["dislikes"] = sorted(dislikes)
        profile["top_preferences"] = profile["interests"][:8]
        profile["hard_constraints"] = profile["constraints"]
        return profile

    def _snapshot(self, entity_id, scope, payload):
        with self.db.connect() as conn:
            previous = conn.execute("SELECT version,payload FROM v2_snapshots WHERE entity_id=? AND scope=? ORDER BY version DESC LIMIT 1", (entity_id, scope)).fetchone()
            encoded = dump(payload)
            if previous and previous["payload"] == encoded:
                return {**payload, "version": previous["version"]}
            version = previous["version"] + 1 if previous else 1
            conn.execute("INSERT INTO v2_snapshots(entity_id,scope,version,payload,created_at) VALUES(?,?,?,?,?)", (entity_id, scope, version, encoded, now()))
        return {**payload, "version": version}

    def profile(self, couple_id: str, scope: str, entity_id: str, viewer_id: str) -> dict:
        facts = self.list_facts(couple_id, scope, entity_id, viewer_id)
        if scope == "COUPLE":
            return self.derive_couple(couple_id)
        return self._snapshot(entity_id, scope, self._build_profile(entity_id, scope, facts))

    def _members(self, couple_id):
        with self.db.connect() as conn:
            rows = conn.execute("SELECT user_id,role,status FROM v2_memberships WHERE couple_id=? ORDER BY role", (couple_id,)).fetchall()
        if not rows:
            raise KeyError("Couple not found")
        return [dict(row) for row in rows]

    def _allowed(self, couple_id, user_id):
        return [f for f in self.repository.active(couple_id,"PERSON",user_id) if f["privacy_scope"] in {"COUPLE_RECOMMENDATION", "SHARED"} and f["consent_state"] == "granted"]

    def planning_context(self, couple_id: str) -> dict:
        members = self._members(couple_id)
        result = {}
        for index, member in enumerate(members[:2]):
            result["person_a" if index == 0 else "person_b"] = self._build_profile(member["user_id"], "PERSON", self._allowed(couple_id, member["user_id"]), internal=True)
        result["couple"] = self.derive_couple(couple_id)
        return result

    def derive_couple(self, couple_id: str) -> dict:
        members = self._members(couple_id)
        for member in members:
            own_facts = self.repository.active(couple_id, "PERSON", member["user_id"])
            self._snapshot(member["user_id"], "PERSON", self._build_profile(member["user_id"], "PERSON", own_facts))
        if len(members) != 2 or any(m["status"] != "completed" for m in members):
            pending = self._build_profile(couple_id, "COUPLE", [], internal=True)
            pending["awaiting_onboarding"] = True
            return {**pending, "version": 0}
        profiles = [self._build_profile(m["user_id"], "PERSON", self._allowed(couple_id,m["user_id"]), internal=True) for m in members]
        shared_facts = []
        for member in members:
            shared_facts.extend(f for f in self._allowed(couple_id,member["user_id"]) if f["privacy_scope"] == "SHARED")
        shared_facts.extend(f for f in self.repository.active(couple_id,"COUPLE",couple_id) if f["privacy_scope"] == "SHARED" and f["consent_state"] == "granted")
        # Public projection never echoes free text, even if it was marked SHARED.
        shared = self._build_profile(couple_id,"COUPLE",shared_facts,internal=True)
        # Apply each person's corrections independently before combining shared
        # tastes, so A's latest assertion cannot erase B's opposite preference.
        shared_profiles = [self._build_profile(m['user_id'], 'PERSON',
                           [f for f in shared_facts if f['owner_id'] == m['user_id']], internal=True)
                           for m in members]
        shared_dislikes = set().union(*(set(p['dislikes']) for p in shared_profiles))
        shared_interests = set().union(*(set(p['interests']) for p in shared_profiles))
        shared['dislikes'] = sorted(shared_dislikes)
        shared['interests'] = sorted(shared_interests - shared_dislikes)
        shared['interest_weights'] = {tag: max(p['interest_weights'].get(tag, 0) for p in shared_profiles)
                                      for tag in shared['interests']}
        common = set(profiles[0]["interests"]) if profiles else set()
        for profile in profiles[1:]:
            common &= set(profile["interests"])
        shared["interests"] = sorted(((common & PUBLIC_CATEGORIES) | set(shared["interests"])) - shared_dislikes)
        shared["top_preferences"] = shared["interests"][:8]
        shared["shared_interests"] = shared["interests"]
        shared["novelty"] = round(sum(p["novelty"] for p in profiles)/max(1,len(profiles)), 3)
        budgets, strict_budgets = [], []
        for profile in profiles:
            budget = profile["budget"]
            divisor = 2 if budget.get("unit") == "couple" else 1
            if isinstance(budget.get("max"), (int,float)):
                amount = budget["max"] / divisor
                budgets.append(amount)
                if not budget.get("flexible", False):
                    strict_budgets.append(amount)
        if budgets:
            # Flexible amounts are preferences, never a hard cap imposed on the
            # other person. Missing budgets must not turn flexibility into a cap.
            shared["budget"] = {"max": min(strict_budgets or budgets), "unit": "person", "flexible": not strict_budgets}
        shared["derivation"] = {"policy": "shared structured facts plus common category and numeric aggregates", "member_count": len(members), "private_facts_used": False}
        snapshot = self._snapshot(couple_id,"COUPLE",shared)
        with self.db.connect() as conn:
            conn.execute("UPDATE v2_couples SET profile_version=? WHERE id=?", (snapshot["version"],couple_id))
        return snapshot

    def export_entity(self, couple_id: str, scope: str, entity_id: str, viewer_id: str) -> dict:
        facts = self.list_facts(couple_id,scope,entity_id,viewer_id)
        # Raw provenance cannot be exported for a partner-owned shared fact.
        own = [f for f in facts if f["owner_id"] == viewer_id]
        return {"scope": scope, "entity_id": entity_id, "facts": facts, "events": [event for fact in own for event in self.provenance(fact["id"],viewer_id)], "exported_at": now()}

    def delete_entity(self, couple_id: str, scope: str, entity_id: str, viewer_id: str) -> dict:
        self._scope(couple_id,scope,entity_id,viewer_id)
        with self.db.connect() as conn:
            ids = [r["id"] for r in conn.execute("SELECT id FROM v2_facts WHERE couple_id=? AND scope=? AND entity_id=? AND owner_id=?",(couple_id,scope,entity_id,viewer_id))]
            for fact_id in ids:
                conn.execute("DELETE FROM v2_links WHERE fact_id=?",(fact_id,))
                conn.execute("DELETE FROM v2_embeddings WHERE fact_id=?",(fact_id,))
                conn.execute("DELETE FROM v2_events WHERE fact_id=?",(fact_id,))
            # A requested erasure is distinct from ordinary append-only history.
            # Delete the whole owner scope in one statement so supersession links
            # within the set do not break FK-enabled databases.
            conn.execute("DELETE FROM v2_facts WHERE couple_id=? AND scope=? AND entity_id=? AND owner_id=?",(couple_id,scope,entity_id,viewer_id))
            self._remove_index(conn,ids)
            conn.execute("DELETE FROM v2_snapshots WHERE entity_id=? AND scope=?",(entity_id,scope))
            conn.execute("DELETE FROM v2_snapshots WHERE entity_id=? AND scope='COUPLE'",(couple_id,))
        self.derive_couple(couple_id)
        return {"entity_id": entity_id, "deleted_count": len(ids)}

    def ingest_onboarding(self, couple_id, user_id, step, value, privacy_scope="COUPLE_RECOMMENDATION", idempotency_key=None):
        categories = {1:"identity",2:"interests",3:"dislikes",4:"budget",5:"style",6:"practical",7:"experience"}
        if step not in categories:
            raise ValueError("Interview step must be 1 through 7")
        key = "onboarding:" + str(step)
        previous = [f for f in self.repository.active(couple_id,"PERSON",user_id) if f["key"] == key]
        return self.ingest(couple_id,"PERSON",user_id,user_id,categories[step],key,value,privacy_scope,source="onboarding",idempotency_key=idempotency_key,supersedes=previous[-1]["id"] if previous and dump(previous[-1]["value"]) != dump(value) else None)

    def ingest_conversation(self, couple_id, user_id, text, privacy_scope="PRIVATE", idempotency_key=None):
        """Deterministic known patterns; free text is never shared by extraction."""
        pattern = re.compile(r"\b(i like|i love|i dislike|i hate|j'aime|je déteste)\s+([^.!?\n]+)", re.I)
        facts = []
        for index, match in enumerate(pattern.finditer(text)):
            category = "dislikes" if match[1].casefold() in {"i dislike","i hate","je déteste"} else "interests"
            values = [v.strip() for v in re.split(r",|\band\b|\bet\b", match[2]) if v.strip()]
            facts.append(self.ingest(couple_id,"PERSON",user_id,user_id,category,"conversation:" + hashlib.sha256(match[0].casefold().encode()).hexdigest()[:16], {"values":values}, privacy_scope, source="conversation", idempotency_key=(idempotency_key + ':' + str(index)) if idempotency_key else None))
        return facts

    def ingest_feedback(self, couple_id, user_id, date_id, rating, repeat=None, avoid=None, text="", privacy_scope="PRIVATE", idempotency_key=None):
        result = []
        for category, value in (("interests",{"values":repeat or []}), ("dislikes",{"values":avoid or []}), ("review",{"rating":rating,"text":text,"date_id":date_id})):
            result.append(self.ingest(couple_id,"PERSON",user_id,user_id,category,"review:"+date_id+':'+category,value, privacy_scope,source="review",idempotency_key=idempotency_key))
        return result

    def ingest_date_history(self, couple_id, user_id, date_id, value, privacy_scope="PRIVATE"):
        return self.ingest(couple_id,"DATE",date_id,user_id,"history","date:"+date_id,value,privacy_scope,source="date_history")

    def learn(self, couple_id, owner_id, candidates, privacy_scope='PRIVATE',
              interaction_id=None, horizon='durable', auto_share=False):
        """Consolidate explicit assertions; unrelated facts are never overwritten."""
        from datetime import timedelta
        import unicodedata
        if horizon not in {'durable', 'temporary'}:
            raise ValueError('Invalid memory horizon')
        self._scope(couple_id, 'PERSON', owner_id, owner_id)
        learned = []
        prepared = {}
        for candidate in candidates[:30]:
            normalized = ' '.join(unicodedata.normalize('NFKC', candidate.value.strip()).casefold().split())
            normalized = AUTO_SHARE_PREFERENCES.get(normalized, normalized)
            family = 'preference' if candidate.category in {'interests', 'dislikes'} else candidate.category
            candidate_horizon = 'temporary' if horizon == 'temporary' or getattr(candidate, 'horizon', 'durable') == 'temporary' else 'durable'
            prepared[(normalized, family, candidate_horizon)] = candidate
        with self.db.atomic():
            for (_, _, candidate_horizon), candidate in prepared.items():
                value = candidate.value.strip()[:500]
                if not value or candidate.confidence < .7:
                    continue
                canonical = ' '.join(unicodedata.normalize('NFKC', value).casefold().split())
                safe_value = AUTO_SHARE_PREFERENCES.get(canonical)
                effective_privacy = 'SHARED' if auto_share and safe_value and candidate.category in {'interests', 'dislikes'} else privacy_scope
                if safe_value:
                    canonical = safe_value
                    value = safe_value
                family = 'preference' if candidate.category in {'interests', 'dislikes'} else candidate.category
                key = 'learned:' + candidate_horizon + ':' + family + ':' + hashlib.sha256(canonical.encode()).hexdigest()
                active = self.repository.active(couple_id, 'PERSON', owner_id)
                previous = next((f for f in reversed(active) if f['key'] == key and not f['contradicted_by']), None)
                if auto_share:
                    with self.db.connect() as c:
                        last_consent = c.execute(
                            "SELECT privacy_scope FROM v2_facts WHERE couple_id=? AND owner_id=? AND scope='PERSON' AND key LIKE ? ORDER BY updated_at DESC,created_at DESC LIMIT 1",
                            (couple_id, owner_id, 'learned:%:' + family + ':' + hashlib.sha256(canonical.encode()).hexdigest())).fetchone()
                    if last_consent and last_consent['privacy_scope'] != 'SHARED':
                        effective_privacy = last_consent['privacy_scope']
                    for existing in active:
                        values = existing['value'].get('values', []) if isinstance(existing['value'], dict) else []
                        normalized_values = [AUTO_SHARE_PREFERENCES.get(v.casefold(), v.casefold()) for v in values if isinstance(v, str)]
                        if canonical in normalized_values and existing['privacy_scope'] != 'SHARED':
                            effective_privacy = 'PRIVATE'
                if auto_share and previous and previous['privacy_scope'] != 'SHARED':
                    # A prior restriction/revocation always wins over automation.
                    effective_privacy = previous['privacy_scope']
                changed = previous and (previous['category'] != candidate.category or previous['privacy_scope'] != effective_privacy)
                fact = self.ingest(couple_id, 'PERSON', owner_id, owner_id,
                    candidate.category, key, previous['value'] if previous and not changed else {'values': [value]},
                    effective_privacy, 'conversation', confidence=candidate.confidence,
                    supersedes=previous['id'] if changed else None,
                    idempotency_key=interaction_id)
                with self.db.connect() as c:
                    if candidate_horizon == 'temporary':
                        expiry = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
                        c.execute('UPDATE v2_facts SET valid_to=? WHERE id=?', (expiry, fact['id']))
                    self._event(c, fact, 'observed', {'interaction_id': interaction_id, 'horizon': candidate_horizon})
                learned.append(self.repository.get(fact['id']))
            self.derive_couple(couple_id)
        return learned
