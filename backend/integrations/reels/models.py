from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from ipaddress import ip_address
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StrictStr, field_validator


class Category(str, Enum):
    restaurant = "restaurant"
    concert = "concert"
    cinema = "cinema"
    expo = "expo"
    sport = "sport"
    bar = "bar"
    voyage = "voyage"
    autre = "autre"


def source_url(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) > 2048:
        raise ValueError("Lien trop long.")
    u = urlsplit(value)
    if u.scheme != "https" or not u.hostname or u.username or u.password:
        raise ValueError("Le lien doit être une URL HTTPS publique sans identifiants.")
    host = u.hostname.lower()
    if host == "localhost" or host.endswith((".local", ".localhost")):
        raise ValueError("Adresse locale refusée.")
    try:
        address = ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Adresse privée refusée.")
    return value


class NormalizedFields(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_assignment=True)
    category: Category
    tags: Annotated[list[Annotated[StrictStr, Field(min_length=1, max_length=100)]], Field(max_length=20)]
    mood: Annotated[StrictStr, Field(max_length=120)] | None
    budget_hint: Annotated[StrictFloat | StrictInt, Field(ge=0, le=1000000)] | None
    confidence: Annotated[StrictFloat | StrictInt, Field(ge=0, le=1)]

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, values: list[str]) -> list[str]:
        if any(not v.strip() for v in values):
            raise ValueError("Tag vide.")
        return list(dict.fromkeys(v.strip() for v in values))


class TasteSignal(NormalizedFields):
    signal_id: StrictStr
    source: Literal["reel"]
    source_url: StrictStr | None
    extracted_at: StrictStr
    raw_transcript: Annotated[StrictStr, Field(max_length=60000)]

    @field_validator("signal_id")
    @classmethod
    def valid_uuid(cls, value: str) -> str:
        UUID(value)
        return value

    @field_validator("extracted_at")
    @classmethod
    def valid_timestamp(cls, value: str) -> str:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("Fuseau horaire requis.")
        return value

    @field_validator("source_url")
    @classmethod
    def valid_url(cls, value: str | None) -> str | None:
        return source_url(value)


def build_signal(fields: NormalizedFields, transcript: str, source_url: str | None) -> TasteSignal:
    return TasteSignal(
        **fields.model_dump(), signal_id=str(uuid4()), source="reel",
        source_url=source_url, extracted_at=datetime.now(timezone.utc).isoformat(),
        raw_transcript=transcript,
    )
