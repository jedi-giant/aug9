from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class SourcePermission(StrEnum):
    OPEN_DATA = "open_data"
    LICENSED_PARTNER = "licensed_partner"
    LINK_ONLY = "link_only"
    RESEARCH_ONLY = "research_only"
    PROHIBITED = "prohibited"


class EntityType(StrEnum):
    FOOD_VENUE = "food_venue"
    HAWKER_CENTRE = "hawker_centre"
    FOOD_STALL = "food_stall"
    ACTIVITY = "activity"
    EVENT = "event"
    HOTEL = "hotel"
    ATTRACTION = "attraction"
    TOUR = "tour"


class RelationshipType(StrEnum):
    CONTAINS = "contains"
    LOCATED_IN = "located_in"


class FoodProfile(BaseModel):
    entity_id: str
    venue_kind: str
    price_min: float | None = Field(default=None, ge=0)
    price_max: float | None = Field(default=None, ge=0)
    currency: str = "SGD"
    dietary_attributes: list[str] = Field(default_factory=list)
    reservation_url: str | None = None

    @model_validator(mode="after")
    def validate_price_range(self):
        if (
            self.price_min is not None
            and self.price_max is not None
            and self.price_max < self.price_min
        ):
            raise ValueError("price_max must be greater than or equal to price_min")
        return self


class OpeningPeriod(BaseModel):
    entity_id: str
    day_of_week: int = Field(ge=0, le=6)
    opens_at: str
    closes_at: str
    source_id: str


class EventProfile(BaseModel):
    entity_id: str
    starts_at: datetime
    ends_at: datetime | None = None
    category: str | None = None
    organiser: str | None = None
    ticketed: bool | None = None
    price_min: float | None = Field(default=None, ge=0)
    currency: str = "SGD"
    booking_url: str | None = None
    source_url: str
    source_id: str

    @model_validator(mode="after")
    def validate_dates(self):
        if self.ends_at is not None and self.ends_at < self.starts_at:
            raise ValueError("ends_at must be greater than or equal to starts_at")
        return self


class DiscoverySource(BaseModel):
    id: str
    name: str
    permission: SourcePermission
    base_url: str | None = None
    license_name: str | None = None
    attribution: str | None = None
    active: bool = True


class DiscoveryEntity(BaseModel):
    id: str
    entity_type: EntityType
    name: str
    description: str | None = None
    address: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    status: str = "active"
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)


class SourceRecord(BaseModel):
    source_id: str
    external_id: str
    entity_id: str
    source_url: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=utc_now)
    verified_at: datetime | None = None


class FieldProvenance(BaseModel):
    entity_id: str
    field_name: str
    source_id: str
    value: Any
    source_record_id: int | None = None


class IngestionRun(BaseModel):
    id: str
    source_id: str
    status: str = "running"
    records_received: int = 0
    records_upserted: int = 0
    records_rejected: int = 0
    error: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
