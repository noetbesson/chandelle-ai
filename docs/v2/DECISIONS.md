# Decisions

1. Add V2 beside V1; retain all V1 models and routes. Do not modify shared/A/D/F contracts.
2. SQLite SQL facts and append-only events are authoritative. JSON payloads are acceptable for typed bounded subdocuments, not permission checks. Schema migrations are root-owned.
3. Local identity uses member capability tokens (hashed at rest), delivered only on couple creation and explicit local handoff. This is local device privacy, not production authentication. Member headers are required on personal data; a member ID alone never authorizes access. Shared device handoff clears rendered answers. No global listing of tokens.
4. Consent PRIVATE excludes planning; COUPLE_RECOMMENDATION allows internal structured preference influence but not verbatim disclosure; SHARED permits display. Never derive free-text content into shared snapshots. Recompute derived profile on every mutation/revoke.
5. V2 uses independent modules under existing streams; old SQLite couple_profiles remains untouched. Root owns backend/db schema and integrations/domain/API.
6. Frontend Next starter has no installed runtime; implement no-build ES-module SPA under frontend/v2, served by FastAPI at /app (and eventually root with V1 at /v1/demo). Preserve V1 /static resources.
7. No live network tests. Real OpenAI SDK adapter is opt-in and validates structured responses with deterministic fallbacks.
8. Responses SDK verified locally (openai 3.19.2, Responses.parse text_format present) and against official Structured Outputs documentation: https://developers.openai.com/api/docs/guides/structured-outputs . Adapter uses Pydantic parse, store=False, bounded timeout/retry; explanation payload contains public catalog facts and numeric scores only.
9. E receives a backward-compatible optional max_activities parameter (default retains V1 four-stop behavior). V2 explicitly passes 1–3. Persisted V2 UUIDs replace E's reused local plan IDs.
10. C fairness: .60 min(A,B)+.40 mean(A,B), individual .45 + min(.4,.2*interest matches) + .1 saved/liked; shared/query bonuses .05/.08; repeat penalty .2*novelty; distance penalty min(.15,.015*km); greedy category diversity penalty .035 per prior category. All hard exclusions happen first. Demo origin Paris center, conservative 4 km/h walking distance.
11. Onboarding identity field privacy does not alter the public welcome pseudonym; private pronouns/name stay in owner memory. Photo visibility defaults owner-only, including authenticated downloads.
