"""Versioned local V2 SQL store; legacy tables are intentionally untouched."""
from pathlib import Path
import sqlite3

SCHEMA = '''
CREATE TABLE IF NOT EXISTS v2_schema(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS v2_users(id TEXT PRIMARY KEY,name TEXT NOT NULL,token_hash TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS v2_couples(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,onboarding_status TEXT NOT NULL DEFAULT 'in_progress',profile_version INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS v2_memberships(couple_id TEXT NOT NULL REFERENCES v2_couples(id),user_id TEXT NOT NULL REFERENCES v2_users(id),role TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'not_started',current_step INTEGER NOT NULL DEFAULT 1,completed_at TEXT,PRIMARY KEY(couple_id,user_id),UNIQUE(couple_id,role));
CREATE TABLE IF NOT EXISTS v2_answers(couple_id TEXT NOT NULL,user_id TEXT NOT NULL,step INTEGER NOT NULL,payload TEXT NOT NULL,privacy_scope TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(user_id,step));
CREATE TABLE IF NOT EXISTS v2_facts(id TEXT PRIMARY KEY,couple_id TEXT NOT NULL,scope TEXT NOT NULL,entity_id TEXT NOT NULL,owner_id TEXT,category TEXT NOT NULL,key TEXT NOT NULL,value TEXT NOT NULL,tags TEXT NOT NULL DEFAULT '[]',privacy_scope TEXT NOT NULL,consent_state TEXT NOT NULL DEFAULT 'granted',confidence REAL NOT NULL DEFAULT 1,salience REAL NOT NULL DEFAULT 0.5,valid_from TEXT,valid_to TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,last_accessed_at TEXT,reinforcement_count INTEGER NOT NULL DEFAULT 0,supersedes TEXT,contradicted_by TEXT,source TEXT NOT NULL,deleted INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS v2_facts_scope ON v2_facts(couple_id,scope,entity_id,deleted);
CREATE TABLE IF NOT EXISTS v2_events(id TEXT PRIMARY KEY,couple_id TEXT NOT NULL,entity_id TEXT NOT NULL,fact_id TEXT,kind TEXT NOT NULL,payload TEXT NOT NULL,source TEXT NOT NULL,created_at TEXT NOT NULL,idempotency_key TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS v2_entities(id TEXT PRIMARY KEY,couple_id TEXT NOT NULL,kind TEXT NOT NULL,label TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_links(fact_id TEXT NOT NULL,entity_id TEXT NOT NULL,PRIMARY KEY(fact_id,entity_id));
CREATE TABLE IF NOT EXISTS v2_embeddings(fact_id TEXT PRIMARY KEY,provider TEXT NOT NULL,model TEXT NOT NULL,vector TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_snapshots(entity_id TEXT NOT NULL,scope TEXT NOT NULL,version INTEGER NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(entity_id,scope,version));
CREATE TABLE IF NOT EXISTS v2_activities(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_activity_states(user_id TEXT NOT NULL,activity_id TEXT NOT NULL,state TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(user_id,activity_id));
CREATE TABLE IF NOT EXISTS v2_plans(id TEXT PRIMARY KEY,couple_id TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_reviews(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,user_id TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,idempotency_key TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS v2_uploads(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,user_id TEXT NOT NULL,filename TEXT NOT NULL,mime TEXT NOT NULL,size INTEGER NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_suggestions(id TEXT PRIMARY KEY,couple_id TEXT NOT NULL,state TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,expires_at TEXT NOT NULL,snoozed_until TEXT);
CREATE TABLE IF NOT EXISTS v2_runs(id TEXT PRIMARY KEY,couple_id TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_conversations(id TEXT PRIMARY KEY,couple_id TEXT NOT NULL,user_id TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_messages(id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL,user_id TEXT NOT NULL,content TEXT NOT NULL,created_at TEXT NOT NULL);
INSERT OR IGNORE INTO v2_schema(version) VALUES(1);
CREATE TABLE IF NOT EXISTS v2_availability(user_id TEXT PRIMARY KEY REFERENCES v2_users(id),couple_id TEXT NOT NULL REFERENCES v2_couples(id),payload TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_extensions(name TEXT PRIMARY KEY,version INTEGER NOT NULL,applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
INSERT OR IGNORE INTO v2_extensions(name,version) VALUES('peer_merge',1);
CREATE TABLE IF NOT EXISTS v2_reel_jobs(
 id TEXT PRIMARY KEY,couple_id TEXT NOT NULL REFERENCES v2_couples(id),
 owner_id TEXT NOT NULL REFERENCES v2_users(id),fingerprint TEXT NOT NULL,
 status TEXT NOT NULL,phase TEXT NOT NULL,fact_key TEXT,
 backend TEXT NOT NULL,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS v2_reel_jobs_owner ON v2_reel_jobs(couple_id,owner_id,fingerprint);
INSERT OR IGNORE INTO v2_extensions(name,version) VALUES('reels_memory',1);
'''

class ManagedConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute('PRAGMA journal_mode=WAL')
            connection.executescript(SCHEMA)

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=15, factory=ManagedConnection)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=15000')
        return connection
