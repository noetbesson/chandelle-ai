# Independent QA/security review

Review scope: read-only `backend/domain/onboarding.py`, `backend/db/database.py`, `backend/integrations/openai/__init__.py`; isolated fake-client tests in `backend/tests/test_v2_openai.py`. Findings below reflect the initial implementation and require root integration verification after fixes.

## Executed evidence

Command: `.venv/bin/python -m pytest backend/tests/test_v2_openai.py -q`

Result: **21 passed in 0.06s**. Every enabled-provider test injects a fake client. Tests cover five structured schemas; malformed output; timeout fallback; unknown/duplicate catalog IDs; disabled adapter with a present key; credentials and private prompts absent from logs/status; person-scoped extraction without conversation carryover; explanation payload allowlisting; configurable embedding model and failure fallback. No test makes a live request.

Previously executed catalog command: `.venv/bin/python -m pytest backend/streams/C_discovery/test_v2_discovery.py backend/streams/C_discovery/test_discovery.py -q` — **9 passed in 0.12s**, including four existing discovery regression tests.

## Findings delivered to root

1. **Answer validation / API errors.** Step 1 accepts non-string names through `str(...)` but persistence calls `.strip()` on the raw value. Step 6 compares arbitrary JSON `travel_minutes` against numbers, permitting `TypeError` to escape Pydantic validation for strings/null. Practical arrays are checked only for container type. Add strict bounded strings, bounded finite numbers, and validated short selections to preserve a consistent 422 envelope.
2. **Private identity edit.** Saving step 1 always changes the shared user display name, even for PRIVATE answers. Creation pseudonyms are intentionally shared; keep that public identity separate from a private interview value, or make any public-name change an explicit shared operation.
3. **Crash/retry consistency.** Memory ingestion commits before the corresponding answer row. A crash between commits can create another provenance event on retry because answer ingestion currently has no stable idempotency key. Use a versioned durable answer-operation key or transaction/reconciliation design. A hash alone must allow A→B→A edits correctly.
4. **Completion ordering.** Couple onboarding is marked completed before initial derivation succeeds. Ensure failure/retry cannot leave Home unlocked with an absent initial snapshot; repeat completion should preserve the same profile version unless its contents changed.
5. **Reranking payload boundary.** `explain` projects public catalog fields, but `rerank` serializes its whole caller-provided candidate dictionaries. Root must pass only public fields, ideally reinforce the allowlist within the adapter. An empty ID array is also a valid subset and should not wipe out otherwise valid deterministic recommendations.
6. **Database integrity hardening.** The migration enables foreign keys, but most V2 relationship tables have no declared foreign keys and enums/steps are not SQL constrained. API/service checks must therefore remain the trusted write boundary. Identity foreign keys and v2-prefixed schema preserve V1 tables. Confirm service-level entity authorization before every read/write; SQL presence alone does not establish membership.
7. **Connection lifecycle.** Standard sqlite connection context management commits/rolls back but does not close the connection. `Database.connect()` returns a raw connection; callers should close it or use a managed subclass/context so sustained API traffic does not accumulate open handles.

## Positive boundaries inspected

- Tokens are random, stored hashed, and not returned by status/member reads.
- Interview service authorizes both member identity and couple identity before returning raw answers.
- Status projects member identity/progress and does not enumerate answers or tokens.
- Optional experience free text defaults to PRIVATE.
- SDK exceptions are collapsed into a generic fallback reason without logging exception contents.
- SDK calls use timeout, bounded retry configuration, structured validation and `store=False`.
- Unknown and duplicate candidate IDs fail closed to deterministic catalog IDs.
- API-key presence does not override `OPENAI_ENABLED`.

## Remaining system verification

This focused review does not claim full API authorization, frontend handoff privacy, upload safety, migration reopen, crash injection or the final end-to-end scenario passed. Those are root-owned integration gates. No live OpenAI request was made.
