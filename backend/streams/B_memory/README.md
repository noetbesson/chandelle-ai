# B memory

Local, persistent couple memory. `SQLiteMemoryRepository()` uses
`<repo>/.runtime/couple_memory.sqlite3`; pass a temporary path in tests.

```python
from backend.streams.B_memory import MemoryService, ProfileUpdate, SQLiteMemoryRepository

memory = MemoryService(SQLiteMemoryRepository())
snapshot = memory.update_profile(
    "couple-1", ProfileUpdate(shared_interests=["jazz"], typical_budget=80)
)
snapshot = memory.get_snapshot("couple-1")
```

`CoupleProfile` is the provisional B output. Its `shared_interests`, `dislikes`,
`typical_budget` (total EUR for two), `desired_novelty`, `recent_dates`,
`user_a`, and `user_b` fields map directly to E's local profile model. Extra
fields preserve facts, selections, date history, feedback, and timestamps.

The service also provides `record_selection(couple_id, SelectionRecord)`,
`record_date(couple_id, DateHistoryEntry)`, and
`ingest_feedback(couple_id, FeedbackRecord)`. Updates merge terms by casefolded
identity, with dislikes removing matching interests. A stated budget or novelty
value replaces the previous value. No language model or network calls occur.
