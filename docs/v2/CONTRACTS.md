# V2 contracts (initial)

Database: `backend.db.database.Database(path)`, `.connect()` sqlite3 Row connection. All root-owned tables are documented in the Stockage SQL section below. Service constructors accept Database.

B module `backend.streams.B_memory.service`: `MemoryServiceV2(db)`; `ingest(couple_id, scope, entity_id, owner_id, category, key, value, privacy_scope='PRIVATE', source='manual', tags=None, idempotency_key=None, supersedes=None)` returns fact dict. `list_facts(couple_id, scope, entity_id, viewer_id)` owner/shared filtered. `search(couple_id, scope, entity_id, viewer_id, query, limit=20)` ranked dicts. `update(fact_id, viewer_id, **changes)`, `delete(fact_id, viewer_id)`, `share(fact_id, viewer_id, privacy_scope)`; `profile(couple_id,scope,entity_id,viewer_id)`; `planning_context(couple_id)` returns {person_a: profile,person_b: profile,couple: profile}; profiles have interests/dislikes/budget/novelty/constraints and no private facts in planning. `derive_couple(couple_id)` safe public profile. `export_entity(...)`, `delete_entity(...)`. Exceptions ValueError/PermissionError/KeyError mapped centrally.

C module `backend.streams.C_discovery.service`: `CatalogService(db, memory)`; `seed()`; `browse(query='',category=None,limit=30,offset=0)`; `get(activity_id)`; `set_state(user_id,activity_id,state)`; `discover(couple_id, time_window, budget=None, categories=None, radius_km=None, limit=30)` returns list dicts {activity: catalog dict, candidate: E CandidateActivity serialized, person_a_score,person_b_score,couple_score,components,evidence}. Calls B planning_context separately for all three scopes. Activity catalog payload includes id,title,description,category,tags,price_per_person,currency,duration_minutes,location,neighborhood,indoor,weather_sensitive,accessibility,weekdays,start,end,availability_source,last_verified_at,booking_url,media,popularity,rating,source,demo,hard_constraints.

API prefix /api/v2. Member auth `X-Member-Token`. Creation POST /onboarding/couples {person_a,person_b} returns {couple_id,members:[{id,name,role,token}],status}. Tokens stored only by local browser for explicit device handoff; API never re-lists tokens. GET /onboarding/status?couple_id=... returns status/member names/step/completion, no answers. GET /onboarding/couples/{cid}/members/{uid} requires that member token; returns own answers only. PUT /onboarding/couples/{cid}/members/{uid}/answers {step:1..7,value:object,privacy_scope:PRIVATE|COUPLE_RECOMMENDATION|SHARED}; POST .../complete validates all steps answered/skipped. Ordinary answer default COUPLE_RECOMMENDATION; free text PRIVATE. Steps: 1 identity {name,pronouns}; 2 interests {values:[]}; 3 dislikes {values:[]}; 4 budget {min,max,flexible,unit:person|couple}; 5 style {energy,social,novelty,outdoor,duration}, numbers 0..1; 6 practical {days:[],travel_minutes,dietary:[],accessibility:[]}; 7 experience {text} optional single free-text response. Skipped {skip:true} allowed except identity.

All other routes require member token and derive couple from token. GET /couples/{id}/profile shared safe profile. GET /memories?scope=PERSON&entity_id=...; POST /memories {scope,entity_id,category,key,value,privacy_scope}; PATCH/DELETE /memories/{id}; POST /memories/{id}/share {privacy_scope}; GET /memories/search?scope=&entity_id=&query=. GET /profiles/{scope}/{entity_id}.
GET /activities?query=&category=&limit=&offset=; GET /activities/{id}; POST /activities/{id}/state {state:saved|liked|disliked|neutral}.
POST /recommendations/query {text,budget?,categories:[],radius_km?,activity_count:1..3,max_plans:1..3,mode:offline|openai,time_window?} returns {run_id,plans,trace,mode}. Plans include id,date_plan_id,activities,timeline,total_couple_cost,per_person_cost,person_a_score,person_b_score,couple_score,reason,evidence,status,generated_at,mode,source,kept_ids.
GET /date-plans; GET /date-plans/{id}; PATCH /date-plans/{id} {status?,kept_ids?}; POST /date-plans/{id}/replace {activity_id}; POST /date-plans/{id}/feedback {rating:1..5,activity_ratings:{},text,repeat:[],avoid:[],privacy_scope,idempotency_key}. GET /history; GET /history/{id}. POST /uploads?plan_id=... raw bytes with Content-Type image/png|image/jpeg and X-Filename; GET/DELETE /uploads/{id} authenticated. No multipart dependency.
GET /suggestions; POST /suggestions/check {}; POST /suggestions/{id}/action {action:viewed|accepted|dismissed|snoozed|regenerate}. GET /runs/{id}. GET /health; GET /integrations. Dev POST /dev/seed, /dev/reset {confirmation:'RESET LOCAL V2'} gated environment.
Errors {error:{code,message}}; validation 422, auth 401/403, unknown 404, conflicts/locked 409. Lists return {items,total,limit,offset} where relevant.

## Final additions and clarifications
- `/` and `/app` serve V2; `/v1/demo` serves original V1 UI. All original V1 endpoints and /static assets persist.
- Query accepts optional `required_activity_id`; every generated plan includes it or returns an infeasibility error. `activity_count` is a maximum, allowing fewer stops when time/budget requires.
- `GET /memories/{id}/provenance`, `GET /memories/export/{scope}/{entity_id}`, `DELETE /memories/entity/{scope}/{entity_id}`, and `POST /conversations` are implemented. Personal provenance is owner-only even for shared facts. Entity deletion here is memory-scope erasure, ordinary memory delete keeps append-only audit events.
- Member tokens are required for protected endpoints; a missing/invalid token returns 403. Public onboarding status exposes only original welcome pseudonyms and completion/progress metadata.
- Raw onboarding identity does not rename public welcome pseudonyms. Completing an already completed couple is idempotent. Completion unlock occurs only after successful derivation.
- Reviews default PRIVATE. Recommendation consent can update the submitting person's structured preferences; partner receives neither review text nor raw DATE facts. Photos are owner-only.
- Plans' private implementation snapshots (`_e_plan`, `_profile`, `_candidates`) are never serialized by API; dynamic owner-filtered reviews/photos are never embedded in persisted plan payloads.
- V2 errors consistently use `{error:{code,message}}`; HTTP 422 covers validation and infeasibility, 409 onboarding lock, 403 ownership, 404 missing resources.
- `backend/streams/G_proactive/service.py` owns suggestions using A availability and SQL catalog/history/state; no weather/provider requests are made.
- `DELETE /users/me/data` with `{confirmation:'DELETE MY DATA'}` performs authenticated personal erasure across raw answers, owned memory scopes/events/indexes, conversations/messages, reviews, photos and activity states. It retains only the local capability/membership for restarting onboarding, resets the pseudonym and re-locks planning. Partner data and shared plan records remain; pending suggestions expire.

## Extension de fusion `peer_merge: 1`

Tous les nouveaux endpoints exigent `X-Member-Token` et les deux entretiens terminés. Couple et propriétaire sont dérivés de l’authentification.

- `GET /availability` → `{own_slots,configured,mode:manual|demo,timezone,common_slots,both_configured}`. Aucun créneau individuel du partenaire.
- `PUT /availability` `{slots:[{start,end}]}` remplace les créneaux du membre, 50 maximum. ISO avec offset ou heure locale Paris. Tableau vide = indisponible, pas retour silencieux au mode démo. Écriture persistante et expiration des suggestions en attente.
- `GET /inspirations` → `{items:[fact...]}` pour le membre seulement. Les faits restent également accessibles par les endpoints mémoire existants.
- `POST /inspirations/import` `{platform:manual|google_maps|instagram|tiktok,format:text|csv|json,content,privacy_scope?,signal_at?,horizon?}` → `{items,duplicates,warnings,truncated}`. 1 Mo maximum, 200 entrées distinctes, 8 000 caractères de contenu par entrée. CSV/GeoJSON Maps, JSON Saved/Likes Instagram et listes Likes/Favorites/Share History TikTok reconnues ; pas de messages privés ou scraping.
- `POST /inspirations/{id}/confirm` `{tags:[string],privacy_scope:PRIVATE|COUPLE_RECOMMENDATION|SHARED,horizon:durable|temporary}` → nouveau fait confirmé. L’ID change lors d’une correction (supersession B existante). Suppression/révocation via `/memories/{id}` et `/memories/{id}/share`.
- `POST /activities/compare` `{activity_ids:[1..5 IDs]}` → `{items,known_total_eur,budget_complete,total_couple_cost,composition_limit:3,message}`. Total null si un prix manque.
- `/recommendations/query` accepte aussi `required_activity_ids` (0–3), union avec le champ historique `required_activity_id`. Tous les IDs doivent figurer dans chaque résultat. Le nombre de choix doit rester inférieur ou égal à `activity_count`. Les disponibilités saisies priment sur la fenêtre demandée ; le premier créneau commun faisable est utilisé.
- `POST /date-plans/{id}/booking` → préparation avec actions, prix, nombre de personnes, horaires, liens éventuels, `requires_user_confirmation:true`, `payment_performed:false`. Programme accepté/completed requis ; le mode démo n’a pas de lien réservable.
- `GET /date-plans/{id}/calendar` → `text/calendar`, téléchargement `.ics`, `Cache-Control: private, no-store`. Programme accepté/completed requis ; identité du couple vérifiée.
- `/health` et `/integrations` ajoutent `extensions:{peer_merge:1}` ; `schema_version:1` conservé.
- L’effacement personnel inclut les disponibilités et les inspirations/provenances. Le reset développeur conserve les registres de migration et réinitialise les 76 exemples.

## Organisation du dépôt — 2026-09-26

Le nettoyage ne change aucun endpoint ni schéma de données. `/v2-static` conserve
les quatre assets applicatifs (HTML, CSS et deux modules JavaScript) ; les scripts
de test sont désormais hors de ce répertoire public, sous `frontend/tests/` et
`scripts/verify_frontend_api.py`. Vérification agrégée : `bash scripts/check.sh`.


## Stockage SQL

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

## Extension additive de fusion

- `v2_availability(user_id PRIMARY KEY REFERENCES v2_users, couple_id REFERENCES v2_couples, payload, updated_at)` : uniquement les plages libres du membre ; JSON de `{start,end}` UTC fusionnées. Aucun libellé d’événement privé n’est demandé.
- `v2_extensions(name PRIMARY KEY, version, applied_at)` : entrée `peer_merge=1`, distincte du registre de base V2 afin de conserver ses contrats.
- Inspirations dans `v2_facts`, scope PERSON, propriétaire authentifié, source `inspiration_import`, clé `signal:<sha256>`. Valeur : plateforme, texte fourni, URL canonique, date brute/date normalisée du signal, date d’import, propositions, confirmation, horizon, expiration et valeurs confirmées. Aucun token fournisseur.
- Les imports brouillons ont catégorie `inspiration` ; la confirmation passe à `interests` par supersession. Événements, recherche, consentement et effacement restent ceux de B.

## Réorganisation par stream

Routes, payloads et schéma SQL inchangés. Les imports Python suivent désormais `backend.streams.<lettre>_<nom>.service`. La carte complète et les responsabilités transverses sont dans ARCHITECTURE.md. Les types E restent dans E_orchestrator/models.py.

## Entrée vidéo mémoire

`backend/api/reels.py` est installé par `install_routes`, sans nouveau serveur.
Routes `/api/v2/reels/upload` (POST multipart, option `wait=true`) et
`/api/v2/reels/jobs/{job_id}` (GET propriétaire). Identité uniquement par le jeton
existant ; les champs `couple_id`/`user_id` envoyés dans le formulaire sont refusés.

Le modèle `backend/integrations/reels/models.py:TasteSignal` valide strictement
signal_id, category, tags, mood, budget_hint, source='reel', source_url, confidence,
extracted_at et raw_transcript. Budget/ambiance restent nuls si inconnus. L'URL est
une métadonnée, jamais une adresse de téléchargement.

`backend/streams/B_memory/reels.py` orchestre extraction, transcription,
normalisation et `MemoryServiceV2.ingest`. Un fait PERSON, source inspiration_import,
clé reel:<empreinte>, contient le signal et les propositions avec confirmed=false.
Le parcours D de confirmation reste identique : supersession vers interests,
consentement et horizon. Aucune écriture dans un hypothétique second COUPLE PROFILE.

`v2_reel_jobs` : propriétaire, couple, empreinte, état/phase/backend, code d'erreur,
dates. Aucun audio ni texte brut. Extension `reels_memory=1`, version V2 inchangée.
Déduplication par propriétaire et URL canonique ou hash du fichier. Une URL désigne
le même import même si la légende change : corriger ensuite la mémoire existante.
Un job ne peut pas être consulté par l'autre membre ; l'effacement du profil annule
ses jobs avant qu'ils puissent réécrire des faits. Les vidéos restent temporaires.
