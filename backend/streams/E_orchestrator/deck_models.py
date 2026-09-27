"""HTTP/TypeScript contract extending the existing E DatePlan without replacing it."""
from typing import Annotated,Literal
from pydantic import BaseModel, ConfigDict, Field
from .models import DatePlan, PlannedActivity, Location
from .service import Query

ActivityId=Annotated[str,Field(min_length=1,max_length=200)]
Category=Literal['food','culture','concerts','cinema','outdoors','sport','workshops','nightlife','home','travel']


class SearchConstraints(Query):
    model_config = ConfigDict(extra='forbid')
    activity_count: int = Field(default=2,ge=1,le=3)
    categories: list[Category] = Field(default_factory=list,max_length=10)
    required_activity_ids: list[ActivityId] = Field(default_factory=list,max_length=3)
    max_total_duration_minutes: int = Field(default=360,ge=15,le=1440)
    max_travel_time_minutes: int = Field(default=30,ge=0,le=180)


class DateSearch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    constraints: SearchConstraints = Field(default_factory=SearchConstraints)
    couple_id: str | None = Field(default=None,max_length=100)
    cloud_consent: bool = False


class ActivityReplacement(BaseModel):
    model_config = ConfigDict(extra='forbid')
    activity_id_to_replace: str = Field(min_length=1,max_length=200)
    new_constraints: str | None = Field(default=None,max_length=500)


class DateComposition(BaseModel):
    model_config = ConfigDict(extra='forbid')
    selected_activity_ids: list[ActivityId] = Field(min_length=1,max_length=50)
    search_id: str | None = Field(default=None,max_length=100)


class DeckActivity(PlannedActivity):
    model_config = ConfigDict(extra='allow')
    title: str
    category: str
    source: str
    demo: bool
    description: str
    address: str


class TimelineEntry(BaseModel):
    model_config = ConfigDict(extra='allow')
    type: Literal['travel','activity']
    minutes: int | None = None


class DeckPlan(DatePlan):
    model_config = ConfigDict(extra='allow')
    id: str
    status: Literal['draft','proposed','accepted','completed','cancelled']
    activities: list[DeckActivity] = Field(min_length=1,max_length=50)
    diversity_label: str
    duration_minutes: int
    search_id: str
    kept_ids: list[str]
    timeline: list[TimelineEntry]
    source: str


class CompositionStats(BaseModel):
    candidate_count: int = 0
    combos_generated: int = 0
    selected_activity_ids: list[list[str]] = Field(default_factory=list)
    rejected_count: int = 0
    scoring_backend: str = 'local_deterministic'
    scoring_fallback: str | None = None
    diversity_strength: float = .65


class ActivityChoice(BaseModel):
    id: str
    name: str
    category: str
    start: str | None
    end: str | None
    price_per_person: float | None
    location: Location | None
    address: str
    tags: list[str]
    why: str
    demo: bool
    image_url: str | None = None
    rating: float | None = None
    source: str


    source_url: str | None = None
    kind: str = 'place'
    checked_at: str | None = None
    schedule_status: str = 'unknown'
    availability: str = 'unknown'
    price_unit: str = 'unknown'
    composable: bool = True


class SearchTrace(BaseModel):
    model_config = ConfigDict(extra='allow')
    stage: str


class DateSearchResponse(BaseModel):
    status: str = 'completed'
    empty_reason: str | None = None
    message: str = ''
    trace: list[SearchTrace] = Field(default_factory=list)
    sources: list[dict[str,str]] = Field(default_factory=list)
    searched_at: str | None = None
    cached: bool = False

    activities: list[ActivityChoice] = Field(default_factory=list,max_length=50)
    budget_cap: float | None = None
    max_total_duration_minutes: int = 360
    max_travel_time_minutes: int = 30
    requested_steps: int = 2
    search_id: str
    proposals: list[DeckPlan] = Field(max_length=3)
    warnings: list[str]
    composition: CompositionStats


class DeckContract(BaseModel):
    """Used only to generate a single schema containing all browser request/response types."""
    search: DateSearch
    response: DateSearchResponse
    replace: ActivityReplacement
    compose: DateComposition
