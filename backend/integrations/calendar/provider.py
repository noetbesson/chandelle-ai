"""Shared provider contract, UTC instants and safe errors."""
from datetime import datetime, timezone
from typing import Protocol
from pydantic import BaseModel, ConfigDict, Field, model_validator

UTC = timezone.utc

class CalendarError(ValueError):
    """Only fixed, public codes may cross the API boundary."""

class TimeSlot(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode='after')
    def validate_window(self):
        if self.start.tzinfo is None or self.end.tzinfo is None or self.end <= self.start:
            raise ValueError('Créneau daté avec fuseau et fin après début requis.')
        self.start, self.end = self.start.astimezone(UTC), self.end.astimezone(UTC)
        return self

    def public(self):
        return {**self.model_dump(mode='json'), 'duration_minutes': int((self.end-self.start).total_seconds()/60)}

class CalendarEvent(TimeSlot):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)
    location: str = Field(default='', max_length=500)
    description: str = Field(default='', max_length=2000)

class CalendarProvider(Protocol):
    def get_busy_slots(self, start: datetime, end: datetime) -> list[TimeSlot]: ...
    def create_event(self, event: CalendarEvent, key: str) -> str: ...
    def update_event(self, event_id: str, event: CalendarEvent) -> bool: ...
    def delete_event(self, event_id: str) -> bool: ...

def graph_instant(value: dict) -> datetime:
    # Requests require UTC responses, including all-day and recurring occurrences.
    stamp = datetime.fromisoformat(value['dateTime'].replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        if value.get('timeZone') not in ('UTC', 'Etc/UTC'):
            raise CalendarError('calendar_timezone_unsupported')
        stamp = stamp.replace(tzinfo=UTC)
    return stamp.astimezone(UTC)
