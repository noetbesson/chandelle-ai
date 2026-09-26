from datetime import datetime, timezone

from pydantic import ValidationError
import pytest

from backend.streams.B_memory import (
    DateHistoryEntry,
    FeedbackRecord,
    MemoryService,
    PersonPreferences,
    ProfileUpdate,
    SelectionRecord,
    SQLiteMemoryRepository,
)
from backend.streams.E_orchestrator.adapters import couple_profile_from_b


def test_profile_persists_and_maps_to_e(tmp_path):
    path = tmp_path / "memory.sqlite3"
    memory = MemoryService(SQLiteMemoryRepository(path))
    profile = memory.update_profile(
        "couple-1",
        ProfileUpdate(
            user_a=PersonPreferences(interests=["Jazz"], dislikes=["Crowds"]),
            user_b=PersonPreferences(interests=["Art"]),
            shared_interests=["Cinema", "jazz"],
            dislikes=["Rain"],
            typical_budget=85,
            desired_novelty=0.8,
            source="conversation",
        ),
    )
    assert profile.user_a.interests == ["Jazz"]
    assert profile.shared_interests == ["Cinema", "jazz"]
    assert profile.preference_facts[0].source == "conversation"

    reopened = MemoryService(SQLiteMemoryRepository(path)).get_snapshot("couple-1")
    assert reopened == profile
    e_profile = couple_profile_from_b(reopened.model_dump(mode="json"))
    assert e_profile.typical_budget == 85
    assert e_profile.user_b.interests == ["Art"]


def test_merge_conflicts_and_idempotent_terms(tmp_path):
    memory = MemoryService(SQLiteMemoryRepository(tmp_path / "memory.sqlite3"))
    memory.update_profile("c", ProfileUpdate(shared_interests=["Jazz", "Art"],
                                             user_a=PersonPreferences(interests=["jazz"])))
    profile = memory.update_profile("c", ProfileUpdate(shared_interests=["ART", "Wine"],
                                                        dislikes=["jazz"],
                                                        user_a=PersonPreferences(dislikes=["Jazz"])))
    assert profile.shared_interests == ["Art", "Wine"]
    assert profile.user_a.interests == []
    assert profile.user_a.dislikes == ["Jazz"]
    assert profile.dislikes == ["jazz"]


def test_history_selection_and_feedback_survive_reopen(tmp_path):
    path = tmp_path / "memory.sqlite3"
    memory = MemoryService(SQLiteMemoryRepository(path))
    memory.record_selection("c", SelectionRecord(date_plan_id="plan-1", decision="selected"))
    memory.record_date("c", DateHistoryEntry(date_plan_id="plan-1",
                                              occurred_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
                                              activities=["Jazz club", "Bistro"]))
    memory.ingest_feedback("c", FeedbackRecord(date_plan_id="plan-1", rating=5,
                                                sentiment="positive", liked_tags=["Music"],
                                                disliked_tags=["Crowds"], text="Great night"))
    reopened = MemoryService(SQLiteMemoryRepository(path)).get_snapshot("c")
    assert reopened.recent_dates == ["Bistro", "Jazz club"]
    assert reopened.selections[0].decision == "selected"
    assert reopened.feedback[0].rating == 5
    assert reopened.shared_interests == ["Music"]
    assert reopened.dislikes == ["Crowds"]
    assert reopened.date_history[0].date_plan_id == "plan-1"


def test_validation_and_unknown_couple(tmp_path):
    memory = MemoryService(SQLiteMemoryRepository(tmp_path / "memory.sqlite3"))
    assert memory.get_snapshot("new").couple_id == "new"
    assert memory.get_snapshot("new").user_a is None
    with pytest.raises(ValueError, match="couple_id"):
        memory.get_snapshot(" ")
    with pytest.raises(ValidationError):
        ProfileUpdate(typical_budget=-1)
    with pytest.raises(ValidationError):
        FeedbackRecord(date_plan_id="x", rating=6)
