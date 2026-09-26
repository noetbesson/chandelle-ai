# Data model

All tables v2_ prefixed. Database(path).connect() returns sqlite3 connection with Row factory, foreign keys enabled; use context manager for transactions. Database initializes migrations on construction.

Identity: users(id,name,token_hash); couples(id,created_at,onboarding_status,profile_version); memberships(couple_id,user_id,role,status,current_step,completed_at), unique couple+role. answers(couple_id,user_id,step,payload,privacy_scope,updated_at) primary key user+step. Raw answer provenance in memory events.

Memory: facts(id,couple_id,scope,entity_id,owner_id,category,key,value JSON,tags JSON,privacy_scope,consent_state,confidence,salience,valid_from,valid_to,created_at,updated_at,last_accessed_at,reinforcement_count,supersedes,contradicted_by,source,deleted); events(id,couple_id,entity_id,fact_id,kind,payload JSON,source,created_at,idempotency_key unique); entities(id,couple_id,kind,label), links(fact_id,entity_id); embeddings(fact_id,provider,model,vector JSON,updated_at); snapshots(entity_id,scope,version,payload,created_at). FTS5 optional accelerator, always SQL authorization first.

Catalog activities(id,payload JSON); activity_states(user_id,activity_id,state,updated_at). Domain plans(id,couple_id,status,payload,created_at,updated_at); reviews(id,plan_id,user_id,payload,created_at,idempotency_key unique); uploads(id,plan_id,user_id,filename,mime,size,created_at); suggestions(id,couple_id,state,payload,created_at,expires_at,snoozed_until); runs(id,couple_id,payload,created_at); conversations(id,couple_id,user_id,created_at); messages(id,conversation_id,user_id,content,created_at).

## Persistence and privacy details
Schema version 1 is idempotently applied; foreign keys protect membership identity relationships. Service validation enforces scope/consent/state for JSON-rich records. FTS5 is created by B where supported; missing FTS falls back to deterministic lexical scoring. Stored local semantic metadata never replaces SQL facts. Reopen/migration tests include a fresh Python process and legacy table preservation.

Capability hashes are SHA-256 of random 32-byte URL-safe tokens. Creation returns raw tokens once to the shared local browser; identity handoff is explicit and clears the previous screen. This is local-device role separation, not protection against someone controlling the device or database.

Soft memory deletion preserves append-only events for owner provenance; explicit memory-entity erasure removes that scope's events/facts/indexes/snapshots. Raw interview answers and completed date records are separate retained product data until developer reset; deleting a memory fact does not silently rewrite its original interview event. Uploads have generated UUID filenames and no user-controlled path; downloads use authenticated owner queries and nosniff/private cache headers.

For full personal-data erasure rather than memory-scope erasure, `/users/me/data` deletes the member's raw answers, all owned facts/events, messages, reviews, uploads and activity states, resets their profile and onboarding, and preserves the other member. Shared plan records and minimal local capability/membership remain so the couple can resume with a fresh interview. This path is tested separately from ordinary fact deletion.
