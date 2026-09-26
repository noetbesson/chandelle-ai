"""Contrat Activity officiel ; source_url reste dans les données brutes."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

NonEmpty = Annotated[str, Field(min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Location(StrictModel):
    lat: Annotated[float, Field(ge=-90, le=90)] | None
    lng: Annotated[float, Field(ge=-180, le=180)] | None
    address: NonEmpty | None
    arrondissement: Annotated[int, Field(ge=1, le=20)] | None


class ActivityFields(StrictModel):
    kind: Literal["place", "event"]
    type: NonEmpty
    name: NonEmpty
    description: NonEmpty | None
    tags: list[NonEmpty]
    start: datetime | None
    end: datetime | None
    opening_hours: NonEmpty | None
    price_per_person: Annotated[float, Field(ge=0)] | None
    price_level: NonEmpty | None
    location: Location
    booking_url: HttpUrl | None
    website: HttpUrl | None
    image_url: HttpUrl | None
    rating: Annotated[float, Field(ge=0)] | None

    @model_validator(mode="after")
    def check_dates(self):
        for value in (self.start, self.end):
            if value is not None and value.utcoffset() is None:
                raise ValueError("Un horaire doit inclure son fuseau horaire.")
        if self.start and self.end and self.end < self.start:
            raise ValueError("La fin précède le début.")
        return self


class DiscoveredActivity(ActivityFields):
    source_url: HttpUrl


class SearchResults(StrictModel):
    activities: list[DiscoveredActivity]


class Activity(ActivityFields):
    id: NonEmpty
    source: Literal["openai_web"]
    match_score: None
    why: None
    attribution: Literal["OpenAI web search"]
    fetched_at: datetime | None
