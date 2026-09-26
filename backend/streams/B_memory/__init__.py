"""V1 compatibility exports. Current product code imports .service explicitly."""

from .legacy import (CoupleProfile, DateHistoryEntry, FeedbackRecord, PersonPreferences,
                     PreferenceFact, ProfileUpdate, SelectionRecord)
from .legacy import DEFAULT_DB_PATH, MemoryRepository, SQLiteMemoryRepository
from .legacy import MemoryService

__all__ = ["CoupleProfile", "DateHistoryEntry", "FeedbackRecord", "PersonPreferences",
           "PreferenceFact", "ProfileUpdate", "SelectionRecord", "DEFAULT_DB_PATH",
           "MemoryRepository", "SQLiteMemoryRepository", "MemoryService"]
