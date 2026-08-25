from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


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
