# Architecture

FastAPI V1 preserved; V2 router composes local identity/onboarding, B scoped memory, C persistent catalog, verified E planner through explicit domain adapter, G feed, H conversation ingestion, and optional OpenAI adapter.

SQLite Database owns migrations and short-lived connections with foreign keys, busy timeout and WAL. All V2 tables prefixed v2_. B owns memory repository/service but uses root-provided Database. C owns catalog repository/service using same Database. Root domain service maps consent-filtered B planning context to E models. E remains deterministic, enforcing budget/time/travel and preserving kept activities. V2 adds unique plan IDs, status, reviews, uploads, evidence and durable traces around E.

Privacy boundary: API authenticates X-Member-Token and resolves member/couple server-side. B retrieval accepts viewer_id and denies other-person facts; planning_context is an internal service method returning only consent-allowed structured facts. Public couple summary contains SHARED facts plus safe numeric/category aggregates, never raw private/recommendation free text. Events/provenance exports are owner-only.

Frontend: standalone local HTML/CSS/modules. Server persists onboarding answers/current step and gates planning/main API until both complete. Explicit developer seed/reset is gated by CHANDELLE_DEV=1. Upload bytes stored in ignored .runtime/uploads, metadata SQL, authenticated serving, safe content types.

## Delivered composition
`backend/api/app.py` retains V1 composition and mounts `install_v2`. V2 instances live under app.state.v2, allowing in-process isolated tests with temporary SQL files. Default V1 and V2 databases are separate. Tests may intentionally share a file; prefixed V2 tables preserve legacy couple_profiles. Managed SQL connections close after commit/rollback.

`domain/onboarding.py` owns identity/interview state. `domain/planning.py` maps B planning_context through C CatalogService into E generate/replace, assigns UUIDs, persists plans, exposes only public fields and learns from owner-scoped reviews. G SuggestionService invokes this same query method. H's verified mock calendar function remains the common-slot source; V2 conversation endpoint uses scoped extraction and durable conversations/messages. Provider protocols remain interfaces only.

V2 root URL is /, alias /app, resources /v2-static. Original V1 UI moved to /v1/demo without altering original asset files or API routes. Frontend is deliberately independent of the uninstalled Next starter.
