# Chandelle Night Shift — Master Plan

## Target at wake-up
An offline-first backend V1 that proves Chandelle's central loop using persistent local data:

request → B memory → C discovery → E planning → response → feedback → B memory

plus a proactive G path that can trigger the same pipeline.

## Why this order
B's CoupleProfile is a dependency for personalized discovery and recommendations.
C's candidate output is a dependency for E.
E is already implemented.
H is the user-facing orchestration path across B/C/E.
G depends on availability, memory and the integrated planning pipeline.

## Overnight priorities
P0:
- preserve verified E
- persistent B
- C consuming B
- integrated B→C→E
- feedback persistence
- full tests

P1:
- G proactive path
- H conversational application layer
- run tracing / error visibility

P2:
- adapter skeletons for OpenAI/Dust/Pipelex
- richer mocks and docs

## Non-goals tonight
- production OAuth
- real Google Calendar
- real Instagram import
- real Dust/Pipelex/OpenAI calls in tests
- production booking/payment
- deployment
- GitHub push
- frontend rewrite

## Wake-up demo
A single local command should start the API.
A demo request for a couple should return a DatePlan.
A feedback call should modify the persisted memory.
A second memory read should show the change.
A proactive check should explain whether a date opportunity exists and, when triggered, produce a plan.

## Evidence
Every gate must leave:
- tests actually run
- handoff written
- state updated
- known gaps recorded
