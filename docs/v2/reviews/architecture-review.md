# Chandelle V2 architecture review

Reviewed 2026-09-26. Read-only implementation audit; this file is the reviewer's sole write. Root reports the initial full baseline as 31 passing tests; the reviewer did not rerun it.

## Existing integration map

| Surface | Existing implementation | V2 integration recommendation |
| --- | --- | --- |
| HTTP/UI | `backend/api/app.py`, static HTML/CSS/JS, `/health`, `/v1/date/request`, `/v1/date/replace`, `/v1/date/feedback`, `/v1/couples/{id}/memory`, `/v1/runs/{id}`, `/v1/proactive/check` | Keep V1 routes and static files; mount V2 router and new frontend entry separately. |
| B | `MemoryService`, `MemoryRepository`, `SQLiteMemoryRepository`, one JSON payload per `couple_profiles` row | Add normalized V2 repository/services. Legacy payloads have no privacy model and must not receive V2 private data. |
| C | Packaged Paris JSON, repository protocol, profile/availability/budget/type/tag/dislike filters | Persistent V2 catalog with provenance, separate scoped contexts, hard exclusions, transparent fairness. Convert catalog rows to E candidates through an adapter. |
| E | Typed `TimeWindow`, `CandidateActivity`, `PlanRequest`, `DatePlan`; deterministic scheduling, walking estimates, ranking, replacement | Reuse verified generate/replace functions, supply authorized context and enrich output with persistent UUID, status, evidence, timeline, metadata. |
| H | Bounded regex parser, request/feedback facade, mock Friday calendar | Add structured provider boundary and offline parser; preserve the same planning pipeline. |
| G | Date-recency threshold and candidate count; calls B→C→E | Persist opportunity state/cooldowns; invoke V2 planning service rather than maintaining a second planning implementation. |
| Frontend | FastAPI-served V1 works; `frontend/app/page.tsx` is the Next starter | Keep V1. A no-build V2 module SPA is viable when the Next toolchain is unavailable; frontend-specific AGENTS rules apply to Next edits. |
| Shared/A/D/F | Shared contracts incomplete; availability, connector and booking interfaces are local/mocked | Keep untouched; document V2 adapters and label every demo/provider assertion. |

## Critical integration findings

1. E currently returns `date_001`, `date_002`, etc. on every run. Those are result positions, not durable IDs. V2 must replace these with UUIDs before persisting plans, feedback, suggestions or photos.
2. E currently searches up to four activities. V2 requires one to three. Add a backward-compatible optional plan activity limit or constrain the V2 composition path with regression coverage; do not silently truncate a composed timeline.
3. C and E currently use 0.55 × min + 0.45 × mean. V2 may adopt the requested 0.60/0.40 formula, but must document the final effective formula across both stages and avoid scoring preferences twice.
4. E replacement verifies all kept candidate fields, including match score. V2 must preserve original kept candidate data when profiles change, or deliberately explain and reject newly infeasible replacements. Persist the source plan and its constraints server-side; never trust a client-submitted plan's price/times/kept flags.
5. Legacy B silently merges interests and removes conflicting likes when dislikes arrive. Use a new V2 fact lifecycle with explicit supersession/conflict events; do not route V2 ingestion through this destructive merge.
6. Existing run records are process-local. V2 must persist sanitized traces and plan IDs. A trace should describe counts/stages, not contain raw person facts, prompt content or provider errors that may embed input.

## Privacy and authorization design

Use three distinct projections: owner memory view; internal consented recommendation context; visible shared Couple profile. `COUPLE_RECOMMENDATION` allows computation but does not authorize verbatim display. `SHARED` permits visible sharing. `PRIVATE` stays within its owner scope and must never enter the other person's retrieval or couple planning.

Every query must apply couple membership plus scope/owner policy before ranking, joining provenance, reading FTS hits, exporting, or constructing a snapshot. Returning a filtered top-level fact while leaking its event body, source text, conflict counterpart, linked entity, snapshot, feedback or explanation is still a leak. Shared profile derivation should use an allowlist of structured categories and non-sensitive aggregates; raw experience/review text must not be copied.

Caller-supplied `member_id` is an identity claim, not authorization. Use an opaque local member capability/session for private operations and a couple-level session for common resources. No production authentication is required, but changing a URL or request member ID must not unlock the partner's data. Document that shared-device/local-browser storage and local filesystem access are outside production security guarantees. Handoff must clear private DOM/forms and request caches before the other person starts. Raw credentials/capabilities must not appear in status/list payloads or traces.

Sharing, revocation, correction and deletion must synchronously invalidate/rebuild derived shared facts, profile snapshots, retrieval indexes and embeddings. Historical shared review text needs its own explicit visibility policy. Photos and their metadata inherit the parent review/plan access policy; do not expose `.runtime/uploads` as an unauthenticated static directory.

## Schema and migration recommendations

Root owns migrations and connection setup. Use transactional, monotonic schema versions with foreign keys enabled per connection and busy timeout. Preserve `couple_profiles` intact. New normalized tables should cover users, couples, memberships, onboarding progress/answers, memory events/facts/entities/links, snapshots, embeddings, catalog, activity feedback, conversations/messages, plans/reviews/photos, suggestions/actions and runs. UUID identifiers avoid collisions across scopes.

Memory facts need `couple_id`, entity kind/id, privacy and consent fields, key/category/value, normalized hash, confidence/salience, valid interval, access/reinforcement counters, supersession/contradiction links and timestamps. Events are append-only provenance and reference the fact/version. Embedding provider/model/dimensions/version are metadata separate from SQL truth. FTS5 is optional; initialization must degrade to deterministic lexical matching when unavailable.

Unique keys should enforce onboarding `(member_id, question_key, revision or idempotency_key)`, exact fact dedup within owner/scope, feedback idempotency, and suggestion opportunity signatures. An answer write must transactionally persist provenance, ingest facts, update resume position, invalidate stale derived data and return owner-scoped state. Retrying a completed answer or completion should not multiply events/profile versions. Editing a prior answer must explicitly supersede prior normalized facts.

Onboarding status may expose names, roles, completion timestamps, current phase and `unlocked`; it must not expose answers. Both-complete transition and initial profile version should be atomic. Skipping optional questions needs an explicit persisted answered/skipped marker. Enforce completion checks server-side on V2 main operations, not only in navigation.

## API and domain recommendations

Use `/api/v2` Pydantic request/response models with one error envelope and bounded pagination. Keep owner authorization separate from target entity parameters. Couple/profile/status responses must be intentionally projected, never raw ORM rows or memory objects.

Planning accepts explicit window, budget convention (couple total internally), category, radius, count and mode. Parse → authorized scoped memory → catalog candidates → E composition → persisted enrichment is the shared pipeline for Ask and G. Hard dislikes, accessibility, availability and excluded tags are filters before ranking; a favorable average cannot rescue a violation. Unknown catalog IDs from model output are rejected before plan creation. Provider mode and offline fallback reason are explicit sanitized metadata.

Plans need server-enforced status transitions, kept IDs, original constraints, immutable activity price/source snapshot, score components and source verification flags. Reviews are attributed to one person, with per-activity ratings and declared visibility; learn into that person's memory first. Suggestions persist dedup/cooldown and outcomes; accept can return the existing accepted plan on retry.

Uploads require bounded request size, extension/MIME plus content signature validation, random server filename, fixed root containment, safe inline/download headers, membership checks and paired file/metadata cleanup. SVG and HTML are not photo formats. Resolve failed write/transaction cleanup explicitly.

## Verification priorities

- Re-run all existing 31 tests unchanged alongside V2 tests; preserve V1 route payloads.
- Test raw response serialization with distinctive private sentinel text across partner retrieval, status, shared profile, suggestions, traces, export, reviews and handoff payloads.
- Test wrong member capability and cross-couple IDs on every object route, including uploads and runs.
- Test skip/resume/reopen, duplicate step completion, edit-after-complete, revoke after derived snapshot, and simultaneous completion safety.
- Test catalog hard filters, balanced-vs-one-sided ranking, three separate memory contexts, geography, repeated-date novelty and no-feasible-plan errors.
- Test fake Responses outputs for timeout, malformed structured results, unknown IDs and private-context omissions; deny socket access throughout default integration tests.
- Test accepted/completed plan persistence, review ingestion, photo deletion and suggestion changes in one complete offline scenario.
- Test schema initialization twice and repository/process reopen; static asset serving and JavaScript syntax checks remain useful even without browser binding.

No implementation tests were executed by this review. The initial baseline assertion above is attributed to the root agent.
