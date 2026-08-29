from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, model_validator

from aug9.discovery.models import (
    CommercialStatus,
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    EvidenceDirection,
    FieldProvenance,
    FoodEvidence,
    FoodEvidenceDimension,
    FoodEvidenceType,
    FoodProfile,
    OpeningPeriod,
    RelationshipType,
    SourcePermission,
    SourceRecord,
)
from aug9.discovery.repository import DiscoveryRepository


DOMAIN_SCHEMA_VERSION = "aug9.food-domain.v1"
INGESTABLE_PERMISSIONS = {
    SourcePermission.OPEN_DATA,
    SourcePermission.USER_PROVIDED,
    SourcePermission.LICENSED_PARTNER,
    SourcePermission.LEGAL_REVIEWED,
}


class DomainSource(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    name: str = Field(min_length=2, max_length=160)
    permission: SourcePermission
    attribution: str = Field(min_length=2, max_length=500)
    base_url: HttpUrl | None = None
    license_name: str | None = Field(default=None, max_length=160)


class DomainLocation(BaseModel):
    address: str | None = Field(default=None, max_length=500)
    postal_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    latitude: float | None = Field(default=None, ge=1.1, le=1.5)
    longitude: float | None = Field(default=None, ge=103.6, le=104.1)
    unit_number: str | None = Field(default=None, max_length=80)
    neighbourhood: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def coordinates_are_complete(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        if not any((self.address, self.postal_code, self.latitude is not None)):
            raise ValueError("location requires an address, postal code, or coordinates")
        return self


class DomainParent(BaseModel):
    external_id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=240)
    entity_type: EntityType
    location: DomainLocation | None = None

    @model_validator(mode="after")
    def parent_type_is_container(self):
        if self.entity_type not in {EntityType.HAWKER_CENTRE, EntityType.FOOD_VENUE}:
            raise ValueError("parent entity_type must be hawker_centre or food_venue")
        return self


class DomainPrice(BaseModel):
    currency: str = Field(default="SGD", pattern=r"^[A-Z]{3}$")
    minimum: float | None = Field(default=None, ge=0)
    maximum: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def range_is_valid(self):
        if self.minimum is not None and self.maximum is not None and self.maximum < self.minimum:
            raise ValueError("price maximum must be greater than or equal to minimum")
        return self


class DomainFoodProfile(BaseModel):
    venue_kind: str = Field(min_length=2, max_length=80)
    cuisines: list[str] = Field(default_factory=list, max_length=30)
    signature_dishes: list[str] = Field(default_factory=list, max_length=50)
    dietary_attributes: list[str] = Field(default_factory=list, max_length=30)
    price: DomainPrice = Field(default_factory=DomainPrice)
    reservation_url: HttpUrl | None = None


class DomainOpeningPeriod(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    opens_at: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    closes_at: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class DomainEvidence(BaseModel):
    external_id: str = Field(min_length=1, max_length=160)
    dimension: FoodEvidenceDimension
    evidence_type: FoodEvidenceType
    direction: EvidenceDirection
    claim_key: str = Field(min_length=2, max_length=80)
    value: dict[str, Any] | list[Any] | int | float | bool
    dish_name: str | None = Field(default=None, max_length=200)
    confidence: float = Field(ge=0, le=1)
    commercial_status: CommercialStatus = CommercialStatus.ORGANIC
    source_url: HttpUrl | None = None
    observed_at: datetime
    expires_at: datetime | None = None


class DomainProvenance(BaseModel):
    source_url: HttpUrl | None = None
    observed_at: datetime
    verified_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)


class DomainPlace(BaseModel):
    external_id: str = Field(min_length=1, max_length=160)
    entity_type: EntityType
    name: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=2000)
    status: str = Field(default="active", pattern=r"^(active|inactive|closed)$")
    location: DomainLocation
    parent: DomainParent | None = None
    food_profile: DomainFoodProfile | None = None
    opening_hours: list[DomainOpeningPeriod] = Field(default_factory=list, max_length=40)
    contact: dict[str, Any] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)
    evidence: list[DomainEvidence] = Field(default_factory=list, max_length=100)
    provenance: DomainProvenance

    @model_validator(mode="after")
    def food_profile_matches_entity(self):
        food_types = {EntityType.FOOD_VENUE, EntityType.FOOD_STALL}
        if self.entity_type not in food_types | {EntityType.HAWKER_CENTRE}:
            raise ValueError(
                "food domain entity_type must be food_venue, food_stall, or hawker_centre"
            )
        if self.entity_type in food_types and self.food_profile is None:
            raise ValueError("food_venue and food_stall records require food_profile")
        if self.entity_type is EntityType.FOOD_STALL and self.parent is None:
            raise ValueError("food_stall records require a parent")
        return self


class FoodDomainDocument(BaseModel):
    schema_version: str
    generated_at: datetime
    source: DomainSource
    places: list[DomainPlace] = Field(min_length=1, max_length=50_000)

    @model_validator(mode="after")
    def document_is_valid(self):
        if self.schema_version != DOMAIN_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {DOMAIN_SCHEMA_VERSION}")
        if self.source.permission not in INGESTABLE_PERMISSIONS:
            raise ValueError("source permission does not allow ingestion")
        identifiers = [place.external_id for place in self.places]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("place external_id values must be unique")
        return self


@dataclass(frozen=True)
class FoodDomainImportSummary:
    run_id: str
    received: int
    upserted: int
    rejected: int


class FoodDomainImporter:
    def __init__(self, repository: DiscoveryRepository) -> None:
        self.repository = repository

    def run(self, path: str | Path) -> FoodDomainImportSummary:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        document = FoodDomainDocument.model_validate(payload)
        source = DiscoverySource(
            id=document.source.id,
            name=document.source.name,
            permission=document.source.permission,
            attribution=document.source.attribution,
            base_url=str(document.source.base_url) if document.source.base_url else None,
            license_name=document.source.license_name,
        )
        self.repository.register_source(source)
        run = self.repository.start_ingestion(source.id)
        upserted = rejected = 0
        try:
            for place in document.places:
                try:
                    self.ingest_place(place, source.id)
                    upserted += 1
                except (KeyError, TypeError, ValueError):
                    rejected += 1
            self.repository.complete_ingestion(
                run,
                records_received=len(document.places),
                records_upserted=upserted,
                records_rejected=rejected,
            )
            return FoodDomainImportSummary(run.id, len(document.places), upserted, rejected)
        except Exception as exc:
            self.repository.complete_ingestion(
                run,
                records_received=len(document.places),
                records_upserted=upserted,
                records_rejected=rejected,
                error=type(exc).__name__,
            )
            raise

    def ingest_place(self, place: DomainPlace, source_id: str) -> None:
        parent_id = None
        if place.parent is not None:
            parent_id = self._entity_id(
                source_id, place.parent.external_id, place.parent.entity_type
            )
            self._upsert_parent(place.parent, parent_id, source_id)

        entity_id = self._entity_id(source_id, place.external_id, place.entity_type)
        entity = DiscoveryEntity(
            id=entity_id,
            entity_type=place.entity_type,
            name=place.name,
            description=place.description,
            address=place.location.address,
            postal_code=place.location.postal_code,
            latitude=place.location.latitude,
            longitude=place.location.longitude,
            status=place.status,
            quality_score=self._quality_score(place),
        )
        raw_payload = place.model_dump(mode="json")
        record = SourceRecord(
            source_id=source_id,
            external_id=place.external_id,
            entity_id=entity_id,
            source_url=(
                str(place.provenance.source_url)
                if place.provenance.source_url
                else None
            ),
            raw_payload=raw_payload,
            fetched_at=place.provenance.observed_at,
            verified_at=place.provenance.verified_at,
        )
        provenance = [
            FieldProvenance(
                entity_id=entity_id,
                field_name=field,
                source_id=source_id,
                value=value,
            )
            for field, value in entity.model_dump().items()
            if field not in {"id", "entity_type", "quality_score"} and value is not None
        ]
        self.repository.upsert_entity(entity, record, provenance)

        if place.food_profile is not None:
            food = place.food_profile
            self.repository.upsert_food_profile(
                FoodProfile(
                    entity_id=entity_id,
                    venue_kind=food.venue_kind,
                    price_min=food.price.minimum,
                    price_max=food.price.maximum,
                    currency=food.price.currency,
                    dietary_attributes=food.dietary_attributes,
                    reservation_url=(
                        str(food.reservation_url) if food.reservation_url else None
                    ),
                ),
                source_id=source_id,
                tags={"cuisine": food.cuisines, "dish": food.signature_dishes},
            )
            periods = [
                OpeningPeriod(
                    entity_id=entity_id,
                    day_of_week=item.day_of_week,
                    opens_at=item.opens_at,
                    closes_at=item.closes_at,
                    source_id=source_id,
                )
                for item in place.opening_hours
            ]
            self.repository.replace_opening_hours(
                entity_id, periods, source_id=source_id
            )

        if parent_id is not None:
            self.repository.add_relationship(
                parent_id,
                entity_id,
                RelationshipType.CONTAINS,
                source_id=source_id,
            )
        for item in place.evidence:
            self.repository.upsert_food_evidence(
                FoodEvidence(
                    id=f"food-evidence:{source_id}:{item.external_id}",
                    entity_id=entity_id,
                    external_id=item.external_id,
                    dimension=item.dimension,
                    evidence_type=item.evidence_type,
                    direction=item.direction,
                    claim_key=item.claim_key,
                    value=item.value,
                    dish_name=item.dish_name,
                    confidence=item.confidence,
                    source_id=source_id,
                    source_url=str(item.source_url) if item.source_url else None,
                    observed_at=item.observed_at,
                    expires_at=item.expires_at,
                    commercial_status=item.commercial_status,
                )
            )

    def _upsert_parent(
        self, parent: DomainParent, entity_id: str, source_id: str
    ) -> None:
        if self.repository.get_entity(entity_id) is not None:
            return
        location = parent.location
        entity = DiscoveryEntity(
            id=entity_id,
            entity_type=parent.entity_type,
            name=parent.name,
            address=location.address if location else None,
            postal_code=location.postal_code if location else None,
            latitude=location.latitude if location else None,
            longitude=location.longitude if location else None,
            quality_score=0.8 if parent.location else 0.4,
        )
        self.repository.upsert_entity(
            entity,
            SourceRecord(
                source_id=source_id,
                external_id=parent.external_id,
                entity_id=entity_id,
                raw_payload=parent.model_dump(mode="json"),
            ),
            [
                FieldProvenance(
                    entity_id=entity_id,
                    field_name="name",
                    source_id=source_id,
                    value=parent.name,
                )
            ],
        )

    @staticmethod
    def _entity_id(source_id: str, external_id: str, entity_type: EntityType) -> str:
        safe_id = re.sub(r"[^a-z0-9_-]+", "-", external_id.casefold()).strip("-")
        prefix = "hawker" if entity_type is EntityType.HAWKER_CENTRE else "food"
        return f"{prefix}:{source_id}:{safe_id}"

    @staticmethod
    def _quality_score(place: DomainPlace) -> float:
        fields = (
            place.name,
            place.location.address,
            place.location.postal_code,
            place.location.latitude,
            place.location.longitude,
            place.description,
        )
        return round(sum(value is not None for value in fields) / len(fields), 4)
