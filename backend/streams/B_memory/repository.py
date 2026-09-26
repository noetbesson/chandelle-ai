"""Repository boundary and SQLite implementation for couple memory."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Protocol

from .models import CoupleProfile


DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / ".runtime" / "couple_memory.sqlite3"


class MemoryRepository(Protocol):
    def get(self, couple_id: str) -> CoupleProfile | None: ...

    def save(self, profile: CoupleProfile) -> CoupleProfile: ...


class SQLiteMemoryRepository:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS couple_profiles "
                "(couple_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def get(self, couple_id: str) -> CoupleProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM couple_profiles WHERE couple_id = ?", (couple_id,)
            ).fetchone()
        return CoupleProfile.model_validate_json(row[0]) if row else None

    def save(self, profile: CoupleProfile) -> CoupleProfile:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO couple_profiles (couple_id, payload) VALUES (?, ?) "
                "ON CONFLICT(couple_id) DO UPDATE SET payload = excluded.payload",
                (profile.couple_id, profile.model_dump_json()),
            )
        return profile
