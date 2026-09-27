# V2 contracts (initial)

## Profondeur de recherche, 27 septembre 2026

La trace `web_search` ajoute `tool_calls`, `search_calls`, `source_count`,
`unknown_tool_actions` et `tool_limit`. Ces nombres ne sont pas le nombre de cartes.
Ils sont nulls pour les anciennes réponses sans mesures. Le cache change de version
et inclut les plafonds d'appels et de fiches. Valeurs par défaut 4 et 16, aucun
nouveau fournisseur ni pipeline. Les plafonds financiers restent des réservations.


## Recherche commune, contrat actualisé au 27 septembre 2026

`POST /api/v2/dates/search` et `/api/dates/search` utilisent la même fonction E.
Les alias `/api/v2/recommendations/query` et `/api/v2/discovery/web` délèguent aussi à
ce parcours ; ils ne constituent plus des collecteurs séparés. Les routes de lecture
`/activities` et `/activities/real` restent compatibles mais renvoient une liste vide
et invitent à lancer une recherche. Les anciennes recherches V1 renvoient HTTP 410.

Réponse : `search_id`, `activities`, `proposals`, `status`, `empty_reason`, `message`,
`trace`, `warnings`, `sources`, `searched_at`, `cached`, limites et contraintes de composition.
Une activité porte son URL source, la date de consultation, son type (lieu, événement,
séance, itinéraire, créneau), `schedule_status`, `availability` et `composable`.
Prix, localisation et heures sont nullables. Un champ inconnu ne vaut pas zéro.
Les citations attestent une référence, pas une validation indépendante de chaque fait.

`trace` : empreinte de requête sans texte brut ; mode/fallback et catégories d'analyse ;
volume brut web ; validation schéma/citations ; avant/après de chaque filtre, nombre
retiré/inconnu ; champs nécessaires à la composition et nombre de combinaisons.
`GET /api/v2/runs/{search_id}` est limité au propriétaire même en cas d'échec avant
création du pool. Les instantanés privés ne sont pas transmis au partenaire.

`v2_web_cache` : cache privé six heures, par propriétaire et critères. `v2_activities` :
cache de faits publics, upsert sur identifiant déterministe URL + nom + date pour les
événements datés. Ce cache n'est jamais parcouru comme catalogue de secours. Remplacer
et composer revalident uniquement les identifiants du pool de recherche sauvegardé.
Une panne n'efface pas les faits ; la recherche en échec ne les affiche pas à la place.
Les anciens enregistrements explicitement `demo=true` sont retirés au démarrage ;
les profils, faits de mémoire et historiques ne sont pas effacés.


Database: `backend.db.database.Database(path)`, `.connect()` sqlite3 Row connection. All root-owned tables are documented in the Stockage SQL section below. Service constructors accept Database.

B module `backend.streams.B_memory.service`: `MemoryServiceV2(db)`; `ingest(couple_id, scope, entity_id, owner_id, category, key, value, privacy_scope='PRIVATE', source='manual', tags=None, idempotency_key=None, supersedes=None)` returns fact dict. `list_facts(couple_id, scope, entity_id, viewer_id)` owner/shared filtered. `search(couple_id, scope, entity_id, viewer_id, query, limit=20)` ranked dicts. `update(fact_id, viewer_id, **changes)`, `delete(fact_id, viewer_id)`, `share(fact_id, viewer_id, privacy_scope)`; `profile(couple_id,scope,entity_id,viewer_id)`; `planning_context(couple_id)` returns {person_a: profile,person_b: profile,couple: profile}; profiles have interests/dislikes/budget/novelty/constraints and no private facts in planning. `derive_couple(couple_id)` safe public profile. `export_entity(...)`, `delete_entity(...)`. Exceptions ValueError/PermissionError/KeyError mapped centrally.

C module `backend.streams.C_discovery.service`: `CatalogService(db, memory)`; `seed()`; `browse(query='',category=None,limit=30,offset=0)`; `get(activity_id)`; `set_state(user_id,activity_id,state)`; `discover(couple_id, time_window, budget=None, categories=None, radius_km=None, limit=30)` returns list dicts {activity: catalog dict, candidate: E CandidateActivity serialized, person_a_score,person_b_score,couple_score,components,evidence}. Calls B planning_context separately for all three scopes. Activity catalog payload includes id,title,description,category,tags,price_per_person,currency,duration_minutes,location,neighborhood,indoor,weather_sensitive,accessibility,weekdays,start,end,availability_source,last_verified_at,booking_url,media,popularity,rating,source,demo,hard_constraints.

Collecte externe distincte : `backend.streams.C_discovery.run_discovery` utilise Responses avec `web_search` uniquement sur lancement explicite et si `DISCOVERY_ENABLE_LIVE=true`. Elle écrit le brut dans `data/raw/` et la liste validée dans `data/activities.json`. Contrat de cette liste : `backend/shared/activity.json`, avec `source=openai_web`, `match_score=null` et `why=null`. Le lecteur `backend.streams.C_discovery.data.load_activities()` ne fait que lire ce fichier local. Aucun chargement automatique dans les tables `v2_activities` ni adaptation vers `CandidateActivity` n'est inclus dans ce transfert ; les deux contrats ne doivent pas être confondus.

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

## Extension calendar_proactive=1 (26 septembre 2026)

Routes ajoutées dans la même API et authentifiées par X-Member-Token : GET `/api/calendar/connect/{google|outlook}` (ou `/api/v2/calendar/connect/...`, option `format=json` pour le front), callback GET `/api/calendar/callback/{provider}` public mais lié à state/PKCE/cookie ; GET `/api/v2/calendar/status`, POST `/api/v2/calendar/sync`, DELETE `/api/v2/calendar/connection`. Une origine OAuth différente de celle du navigateur est refusée. Aucun token fournisseur dans une réponse.

GET `/api/v2/calendar/plans/{pid}` retourne l'aperçu, la revision SHA-256, le nombre d'accords et le résultat de son propre calendrier. POST `.../{pid}/confirm` accepte seulement `{revision}`. Les deux membres doivent confirmer la même révision ; le statut de programme doit être accepted ou cancelled. Une reprise conserve les succès individuels. L'export .ics existant reste inchangé. TimeSlot utilise des instants avec fuseau ; sa vue publique inclut duration_minutes. Les anciennes heures sans fuseau des parcours manuels restent interprétées par A en Europe/Paris avec contrôle DST.

GET/PUT `/api/v2/proactive/settings`, PUT `/api/v2/proactive/mood-consent` (`{enabled:bool}`), POST `/api/proactive/trigger/{couple_id}` et alias V2 (`{demo:false}` par défaut). Démo true réservée au serveur CHANDELLE_DEV. GET `/api/v2/notifications`, POST `/api/v2/notifications/{id}/read`. Les identifiants étrangers ne donnent accès à aucune donnée ; ni source d'humeur privée ni identifiant d'événement fournisseur n'est rendu au partenaire.

Tables ajoutées : v2_calendar_connections, v2_calendar_oauth, v2_calendar_approvals, v2_calendar_events, v2_notifications, v2_notification_reads, v2_proactive_settings, v2_proactive_runs, v2_mood_cloud, v2_mood_cache. Aucune seconde base. Suppression des accès et consentements lors de l'effacement personnel. Le scheduler n'est actif qu'avec PROACTIVE_SCHEDULER_ENABLED=1 et un serveur vivant ; son état réel est exposé dans proactive/settings. Cette extension ne garantit pas la vérification des activités issues du catalogue de démo ni une réplication des éditions distantes dans les DatePlans.

## Mémoire continue

- `POST /conversations` conserve les champs existants `text`, `privacy_scope`,
  `mode`, et accepte `conversation_id?`, `idempotency_key?`, `learn=true`,
  `auto_share=true`, `horizon=durable|temporary`. Sans confidentialité explicite,
  seuls les goûts de l'allowlist sont SHARED ; le reste reste PRIVATE. Confidentialité
  explicite et restrictions antérieures priment sur l'automatisme.
- Réponse : `{conversation_id,interaction_id,facts,mode,replayed}`. Les répétitions
  consolident les faits ; les messages restent distincts sauf renvoi idempotent.
  Réutiliser une clé avec un autre payload est une erreur 422.
- `GET /conversations?limit=100&offset=0` liste les échanges du membre (1–100 par page), avec total ;
  `GET /conversations/{sid}` rend les messages de cet échange au seul propriétaire.
- `/recommendations/query` conserve le texte dans le journal de l'auteur et ajoute
  `conversation_id` à sa réponse. Les faits privés n'influencent pas le couple.
- `v2_memory_interactions` : reçu par interaction, user/conversation/message avec
  FK cascade, request_key unique par user, fingerprint, fact_ids JSON et mode.
  Registre additif `continuous_memory=1` ; base `v2_schema=1` inchangée.
- Faits durables : `valid_to=NULL`. Envies : `valid_to=maintenant+30 jours` ;
  exclusion automatique du profil/recherche après expiration. Clés `learned:`
  séparées par horizon. Événement `observed` relie le fait à son interaction.
- Le journal n'est pas un chatbot génératif : il montre les messages réellement
  conservés et les faits extraits. OpenAI reste opt-in via l'adaptateur existant.
  Repli local limité aux assertions/préférences explicites françaises/anglaises.

## Discover vocal Gradium

- `POST /discover/chat` : `{messages: string[0..8], recommend: boolean=false}`,
  chaque message 1–1500 caractères ; réponse `{reply, plans, ...run éventuel}`.
  Historique temporaire fourni par le navigateur, pas de lecture du journal.
  H injecte un appel E avec budget extrait, 2 activités maximum et 1 plan.
- `POST /voice/transcribe` : corps WAV PCM mono 16 bits, Content-Type audio/wav,
  plafond 4 500 000 octets et durée maximale 46 s (tolérance autour des 45 s UI).
  Réponse `{text}`. Audio non conservé.
- `POST /voice/speak` : `{text: string(1..1500)}` → audio/wav, cache privé no-store.
- Les trois endpoints exigent X-Member-Token et les entretiens terminés. Erreurs
  fournisseur nettoyées en 503 ; validation 422, type audio 415, taille 413.
- `/integrations` ajoute `gradium:{enabled,configured,available}` sans clé.
- Variables : GRADIUM_ENABLED/API_KEY/VOICE_ID, GRADIUM_STT_MODEL/TTS_MODEL.
  Aucun schéma SQL modifié. Protocole et lancement dans GRADIUM.md.

Interface vocale compacte : aucun changement HTTP. La transcription reste interne
au navigateur et est envoyée automatiquement à /discover/chat à la fin d’une
prise. Aucun champ transcript ni stockage supplémentaire introduit.

## Import Google Calendar

- `POST /availability/google-calendar` : `{url: adresse iCal Google HTTPS,
  start_date: YYYY-MM-DD, days:1..31=14, daily_start:HH:MM=08:00, daily_end:HH:MM=23:00}`.
  Entretien terminé et token requis. Réponse état habituel + imported_slots.
  Validation 422 ; téléchargement inaccessible 502. Aucun remplacement en échec.
- `GET /availability` ajoute `calendar_import:null|{imported_at,start_date,days,
  daily_start,daily_end}` pour le propriétaire uniquement. `mode` historique
  manual/demo conservé ; les métadonnées distinguent une importation de la saisie.
- Saisie manuelle et imports acceptent au maximum 500 créneaux (ancienne borne 50
  élargie). Horaires de sortie Paris, trous libres >=30 min, ni titre ni URL stockés.
- Nouvelle table additive `v2_calendar_imports(user_id PK REFERENCES v2_users ON
  DELETE CASCADE,couple_id,imported_at,start_date,days,daily_start,daily_end)`.
  Registre google_ical=1 ; v2_schema reste 1. Écriture avec v2_availability dans
  la même transaction, effacement personnel/reset inclus.
- /integrations.calendar expose google_ical_import=true, automatic_sync=false.
  /health et /integrations annoncent l’extension google_ical.
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

## Contrat de partage mobile PWA

Manifest share_target : POST multipart /api/receive-share, champs title/text/url
et fichier video (MP4/MOV). Le service worker valide et conserve temporairement le
contenu dans IndexedDB chandelle-share-inbox, puis redirige en 303 vers
/partager?id=<UUID>. Aucun titre, URL source, jeton ou texte dans cette redirection.
La route serveur de secours ne consomme pas le fichier et renvoie 409 avec aide.

Le navigateur conserve au maximum cinq brouillons pendant 24 h (nettoyage au
prochain accès), éventuellement owner=couple_id:member_id et jobId. Ces données
ne sont pas la mémoire et ne sont pas synchronisées vers d'autres appareils.
L'absence de session ouvre l'onboarding, le profil n'est jamais choisi par défaut.
Après choix, la même identité est vérifiée avant/après chaque réponse asynchrone.
La date de réception n'est jamais envoyée comme date d'un ancien like ou favori.

Un fichier passe par l'upload authentifié existant et son job. Un lien/texte seul
passe par /api/v2/inspirations/import après confirmation explicite. Les deux
produisent des propositions privées à confirmer dans l'écran Inspirations.
Aucun nouveau schéma SQL, fournisseur ou backend. Routes publiques ajoutées :
/manifest.json, /sw.js, /installer, /partager. La page de réception est no-store.

## Discover web et budget OpenAI

POST /api/v2/discovery/web, authentification et entretiens terminés :
`{text: string[3..800], cloud_consent: bool, use_shared_interests: bool=false}`.
Sans consentement : 422. Sans activation/clés, quota dépassé ou fournisseur en erreur : résultat status=unavailable avec reason sûr et sources vides. Succès : status=completed, mode=openai_web, answer, segments avec URLs de citations, sources, searched_at, verification, model, cached. L'UI échappe tous les textes et rend les références HTTPS publiques cliquables. Aucun HTML fournisseur exécuté. Une réponse sans recherche terminée et sans citation est refusée.

`v2_web_cache(owner_id,cache_key,payload,created_at)` : clé incluant requête, thèmes, date et modèle ; six heures, nettoyage à l'accès, suppression lors de l'effacement du profil. Aucun cache partagé entre membres. Les tentatives simultanées restent soumises au quota ; le cache ne constitue pas un ordonnanceur distribué.

GET /api/v2/ai/budget authentifié : compteurs de réserves quotidiennes et totales en USD, pas une mesure du crédit distant. `v2_ai_calls` contient seulement date, genre d'appel, réserve, résultat et tokens numériques disponibles. Aucun prompt, clé ni identifiant de personne. BEGIN IMMEDIATE réserve avant l'appel, sans remboursement automatique en cas d'échec. Indépendant du reset démo. Extension SQL ai_discovery=1, même base.

POST /api/v2/conversations conserve son contrat et ajoute reply/fallback à la réponse. Le choix mode=openai dans le formulaire matérialise le consentement d'envoyer le message à OpenAI. La réponse UI est un accusé d'enregistrement des faits, pas encore une réponse conversationnelle générée. Les budgets extraits ne sont enregistrés que si leur unité personne/couple est explicitée.

### Lancement local Windows avec OpenAI

1. Copier `backend/integrations/.env.example` à la racine du dépôt sous `.env` (ignoré par Git). Ne pas écraser un fichier .env préexistant.
2. Renseigner OPENAI_API_KEY dans ce fichier local, jamais dans le chat. Mettre OPENAI_ENABLED=1 et OPENAI_WEB_ENABLED=1. Conserver les limites 1 et 10 pour commencer. Laisser REELS_LIVE_ENABLED=0 : les fournisseurs vidéo ont une tarification indépendante.
3. Depuis la racine : `powershell -File scripts/run_ai.ps1 -Port 8000`. Ce lanceur charge les variables OPENAI_/REELS_ sans exécuter le contenu du fichier. Le lancement historique uvicorn ne charge pas automatiquement .env. Le script lie le serveur à 127.0.0.1, sans déploiement.
4. Ouvrir http://127.0.0.1:8000, terminer les profils, puis Discover > Rechercher une sortie sur le web. Cocher le consentement et envoyer une demande précise. Voir le quota via le bouton dédié. Dans Memories, utiliser le nouveau formulaire pour alimenter le profil.

Modèles conservés : gpt-4.1-mini pour texte/web ; text-embedding-3-small pour l'adaptateur d'embedding qui reste non utilisé par la mémoire locale. Modifier le modèle exige de revoir sa réserve, sinon model_not_budgeted. Les plafonds de réserve ne garantissent pas le montant de la facture fournisseur ; garder un compte/projet de test dédié et contrôler la consommation réelle.

Références consultées : [outil web OpenAI](https://developers.openai.com/api/docs/guides/tools-web-search), [tarification](https://developers.openai.com/api/docs/pricing). Le web_search ajoute son coût aux tokens ; gpt-4.1-mini applique un bloc de tokens de recherche. Les réserves locales sont des choix prudents de fonctionnement, pas des prix contractuels.

Le smoke historique scripts/live_openai_smoke.py exige toujours RUN_LIVE_OPENAI_SMOKE=1 et utilise désormais la même base et le même quota. Il n'a pas été exécuté en live lors de cette tranche.

## Cache Discovery consultable

`GET /api/v2/activities/real` requiert les deux entretiens terminés et retourne `{items:[Activity...],total}` depuis `backend/streams/C_discovery/data/activities.json`. Les Activity sont revalidées, sans appel réseau, et ne sont pas ajoutées à `v2_activities` ni aux candidats de planification. Le frontend les montre dans une section distincte avec lien vers `website`. Prix, horaires, coordonnées et score inconnus restent `null`. Un cache absent donne une liste vide.


## Ask web : extension compatible

WebQuery accepte un objet plan optionnel : budget (0..10000, total couple), date ISO, time ISO, activity_count (1..3), radius_km (1..200), categories (10 maximum). Ces contraintes entrent dans la clé de cache et le prompt ; la réponse contient requested_plan pour afficher les critères et leurs limites. Aucun changement aux contrats /recommendations/query ni aux programmes persistés. Le consentement est obligatoire pour les modes OpenAI dans Ask. use_shared_interests reste opt-in et ne transmet que les thèmes publics autorisés. Une sélection du catalogue se compose en mode local.


## Deck E, 26 septembre 2026

`POST /api/dates/search` reçoit `{constraints: SearchConstraints, couple_id?, cloud_consent}` et renvoie `{search_id, proposals: DeckPlan[], warnings, composition}`. Alias identique `/api/v2/dates/search`. Maximum et cible : trois programmes distincts ; moins seulement si le pool ne comporte pas trois combinaisons faisables, avec raison explicite. Zéro combinaison donne `proposals:[]`. `constraints` conserve Query et ajoute `max_total_duration_minutes` (15..1440, défaut 360), `max_travel_time_minutes` (0..180, défaut 30). Nombre exact d'étapes 1..3. Les catégories sont bornées au vocabulaire C. Les deux entretiens et le jeton du membre sont obligatoires ; le couple du corps ne peut pas changer l'identité.

`POST /api/dates/{pid}/replace-activity` reçoit `{activity_id_to_replace,new_constraints?}` et renvoie le programme mis à jour avec le même ID. Édition uniquement draft/proposed et activité non verrouillée. Réutilise le pool enregistré, conserve les autres étapes et leur ordre. Aucun appel discovery fournisseur. Les règles récentes de B/A/C peuvent invalider un ancien choix : rejet explicite, aucune écriture partielle.

`POST /api/dates/compose` reçoit `{selected_activity_ids:[1..3 IDs distincts],search_id?}`. Le pool doit provenir d'une recherche du membre connecté dans le même couple. Sans search_id, utilise sa dernière recherche ; le front transmet toujours l'ID. Tri chronologique et vérification complète, puis nouveau programme draft. Ni acceptation ni écriture calendrier implicitement.

`DeckPlan` étend DatePlan : `id`, `status`, `diversity_label`, `duration_minutes`, `search_id`, `kept_ids`, `timeline`, provenance des activités. Le contrat Python génère `frontend/contracts/date-deck.schema.json` et `frontend/src/date-contract.mts` ; `scripts/generate_date_contract.py --check` détecte une divergence. Les champs `_deck`, `_e_plan`, `_profile`, `_candidates` ne sortent jamais de `PlanningService.public`. Aucune nouvelle table ; les anciennes routes et consommateurs sont conservés.

## Cartes individuelles et traitement produit, 27 septembre 2026

`/api/dates/search` et son alias V2 ajoutent une projection ActivityChoice publique :
id, name, category, start/end datés avec fuseau, price_per_person, location, address,
tags, why, demo, image_url, rating et source. Aucune valeur n'est tirée d'une note
privée. Au plus 50 cartes, cinq par catégorie sauf activités déjà proposées.
`proposals` reste compatible. Ajouts : budget_cap, max_total_duration_minutes,
max_travel_time_minutes, requested_steps.

`/api/dates/compose` accepte 1..50 identifiants distincts d'une même recherche.
Les sélections fixées sont vérifiées en temps linéaire, sans étendre la génération
combinatoire des trois programmes. Un lot sans combinaison complète est conservé
sous `_activity_search` dans le payload existant `v2_runs`. Ce champ n'est jamais
renvoyé, et le GET du run vérifie son propriétaire. Les anciennes recherches avec
`_deck` dans `v2_plans` restent utilisables ; même durée de vie de 24 h.

Query/Conversation acceptent `auto` en plus de offline/openai. `auto` suit la
configuration du serveur, avec repli existant, sans enregistrer d'accord fictif.
WebQuery et le formulaire multipart Reels acceptent `processing=standard` (sinon
legacy). Les anciens contrats cloud_consent restent inchangés ; aucun client legacy
n'est activé rétroactivement. Les quotas et l'autorisation d'utiliser un fichier
restent vérifiés. Le traitement d'humeur historique n'est pas activé par la suppression
de son ancien bouton : les autorisations enregistrées et la configuration demeurent.

## Chandelier vocal

Changement de présentation uniquement : contrats HTTP, WAV et stockage inchangés.
Le niveau audio utilisé pour les flammes reste dans le navigateur. Les identifiants
DOM/actions voice-orb sont conservés pour la compatibilité du contrôleur.
## Contrats après fusion Gradium et cartes, 27 septembre 2026

`POST /api/v2/discover/chat` conserve messages/recommend/reply/plans et, lors
d'une recherche, retourne aussi le run_id, les activités sourcées, avertissements
et traces de PlanningService. Le front projette run_id en search_id et plans en
proposals pour le même ActivitySwipeDeck. Composer réutilise le pool privé ; une
activité sans prix ou horaire reste consultable sans devenir un faux programme.
L'identité reste issue de X-Member-Token et des entretiens terminés.

`GET /api/v2/integrations` combine l'état Gradium, le catalogue web_search_only,
les fournisseurs OAuth et google_ical_import. automatic_sync=false concerne
l'absence de synchronisation automatique des événements ; l'import iCal reste
ponctuel. Aucun secret n'est retourné. `/conversations` accepte toujours auto,
ainsi que les champs conversation_id/idempotency_key/horizon/learn de Noé.
