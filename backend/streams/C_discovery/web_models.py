"""Validated web facts. Missing prices, dates and coordinates stay unknown."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from backend.streams.E_orchestrator.models import Location

class WebActivity(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=2,max_length=200)
    category: Literal['food','culture','concerts','cinema','outdoors','sport','workshops','nightlife','home','travel']
    kind: Literal['place','event','screening','route','bookable_slot']
    source_url: str
    description: str = Field(max_length=1000)
    address: str | None = None
    department: str | None = None
    location: Location | None = None
    tags: list[str] = Field(default_factory=list,max_length=12)
    price: float | None = Field(default=None,ge=0,allow_inf_nan=False)
    price_unit: Literal['person','couple','free','unknown'] = 'unknown'
    start: datetime | None = None
    end: datetime | None = None
    schedule_status: Literal['published','proposed','unknown'] = 'unknown'
    availability: Literal['unknown','unavailable','published_slot'] = 'unknown'
    evidence: str = Field(max_length=800)

    @model_validator(mode='after')
    def consistent(self):
        for stamp in (self.start,self.end):
            if stamp is not None and stamp.utcoffset() is None:raise ValueError('Timezone required')
        if self.start and self.end and self.end<=self.start:raise ValueError('Invalid times')
        if self.kind in ('event','screening','bookable_slot') and self.schedule_status=='proposed':raise ValueError('A dated event cannot have invented showtimes')
        if self.price_unit=='free' and self.price!=0:raise ValueError('Free requires documented zero price')
        return self

class WebResults(BaseModel):
    model_config = ConfigDict(extra='forbid')
    activities: list[WebActivity] = Field(max_length=16)
    note: str = Field(max_length=700)
