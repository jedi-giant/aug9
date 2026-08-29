from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class SourcePermission(StrEnum):
    OPEN_DATA = "open_data"
    USER_PROVIDED = "user_provided"
    LICENSED_PARTNER = "licensed_partner"
    LEGAL_REVIEWED = "legal_reviewed"
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
    PLAYGROUND = "playground"


class RelationshipType(StrEnum):
    CONTAINS = "contains"
    LOCATED_IN = "located_in"


class FoodEvidenceDimension(StrEnum):
    FOOD_QUALITY = "food_quality"
    CONTEXTUAL_FIT = "contextual_fit"
    RELIABILITY = "reliability"
    EXPERIENCE = "experience"
    REGULATORY_SAFETY = "regulatory_safety"
    POPULARITY = "popularity"
    DISCOVERY_VALUE = "discovery_value"


class FoodEvidenceType(StrEnum):
    FACTUAL = "factual"
    EDITORIAL = "editorial"
    COMMUNITY = "community"
    BEHAVIOURAL = "behavioural"


class EvidenceDirection(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class CommercialStatus(StrEnum):
    ORGANIC = "organic"
    SPONSORED = "sponsored"
    MERCHANT_SUBMITTED = "merchant_submitted"


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


class FoodListing(BaseModel):
    entity: "DiscoveryEntity"
    profile: FoodProfile
    parent: "DiscoveryEntity | None" = None
    tags: dict[str, list[str]] = Field(default_factory=dict)
    opening_periods: list["OpeningPeriod"] = Field(default_factory=list)


class OpeningPeriod(BaseModel):
    entity_id: str
    day_of_week: int = Field(ge=0, le=6)
    opens_at: str
    closes_at: str
    source_id: str


class FoodEvidence(BaseModel):
    id: str
    entity_id: str
    external_id: str
    dimension: FoodEvidenceDimension
    evidence_type: FoodEvidenceType
    direction: EvidenceDirection
    claim_key: str
    value: Any
    source_id: str
    source_url: str | None = None
    dish_name: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    observed_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None
    commercial_status: CommercialStatus = CommercialStatus.ORGANIC

    @model_validator(mode="after")
    def validate_evidence(self):
        if not self.id.strip() or not self.external_id.strip():
            raise ValueError("Evidence identifiers cannot be empty")
        if not self.claim_key.strip():
            raise ValueError("claim_key cannot be empty")
        if self.dish_name is not None and not self.dish_name.strip():
            raise ValueError("dish_name cannot be empty")
        if self.expires_at is not None and self.expires_at < self.observed_at:
            raise ValueError("expires_at must be greater than or equal to observed_at")
        return self


class GooglePlaceLink(BaseModel):
    entity_id: str
    place_id: str
    match_confidence: float = Field(ge=0.0, le=1.0)
    match_method: str = "automatic"
    matched_at: datetime = Field(default_factory=utc_now)
    manually_verified: bool = False

    @model_validator(mode="after")
    def validate_link(self):
        if not self.entity_id.strip() or not self.place_id.strip():
            raise ValueError("Google place link identifiers cannot be empty")
        if self.match_method not in {"automatic", "manual"}:
            raise ValueError("match_method must be automatic or manual")
        return self


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
