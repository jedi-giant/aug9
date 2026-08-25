import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field, model_validator

from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    EventProfile,
    FieldProvenance,
    SourcePermission,
    SourceRecord,
)
from aug9.discovery.repository import DiscoveryRepository


class GeoResolution(BaseModel):
    address: str
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class AggregationRecord(BaseModel):
    external_id: str
    entity_type: EntityType
    name: str
    address: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    generated_description: str | None = None
    source_url: str | None = None
    raw_facts: dict[str, object] = Field(default_factory=dict)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    category: str | None = None
    organiser: str | None = None
    ticketed: bool | None = None
    price_min: float | None = Field(default=None, ge=0)
    currency: str = "SGD"
    booking_url: str | None = None

    @model_validator(mode="after")
    def validate_event(self):
        if self.entity_type == EntityType.EVENT and self.starts_at is None:
            raise ValueError("Event records require starts_at")
        if self.ends_at is not None and self.starts_at is None:
            raise ValueError("ends_at requires starts_at")
        if self.starts_at and self.ends_at and self.ends_at < self.starts_at:
            raise ValueError("ends_at must not precede starts_at")
        return self


class AggregationAdapter(Protocol):
    def collect(self) -> Iterable[Any]: ...

    def parse(self, raw: Any) -> AggregationRecord: ...


class AggregationGeocoder(Protocol):
    def resolve(self, address: str) -> GeoResolution | None: ...


@dataclass(frozen=True)
class AggregationSummary:
    received: int
    upserted: int
    rejected: int
    run_id: str


class DataAggregationEngine:
    """Governed collection-to-canonical pipeline for approved sources."""

    def __init__(
        self,
        repository: DiscoveryRepository,
        *,
        geocoder: AggregationGeocoder | None = None,
        now: datetime | None = None,
        max_records: int = 500,
    ) -> None:
        if max_records < 1 or max_records > 10_000:
            raise ValueError("max_records must be between 1 and 10000")
        self.repository = repository
        self.geocoder = geocoder
        self.now = now or datetime.now(UTC)
        self.max_records = max_records

    def run(
        self,
        source: DiscoverySource,
        adapter: AggregationAdapter,
    ) -> AggregationSummary:
        if source.permission not in {
            SourcePermission.OPEN_DATA,
            SourcePermission.LICENSED_PARTNER,
            SourcePermission.LEGAL_REVIEWED,
        }:
            raise ValueError(
                f"Source permission '{source.permission.value}' does not allow ingestion"
            )
        self.repository.register_source(source)
        run = self.repository.start_ingestion(source.id)
        received = upserted = rejected = 0
        try:
            for raw in adapter.collect():
                if received >= self.max_records:
                    break
                received += 1
                try:
                    record = adapter.parse(raw)
                    self.ingest(source, record)
                    upserted += 1
                except (KeyError, TypeError, ValueError):
                    rejected += 1
            completed = self.repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=upserted,
                records_rejected=rejected,
            )
        except Exception as exc:
            self.repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=upserted,
                records_rejected=rejected,
                error=type(exc).__name__,
            )
            raise
        return AggregationSummary(received, upserted, rejected, completed.id)

    def ingest(self, source: DiscoverySource, record: AggregationRecord) -> str:
        name = self.clean_text(record.name)
        external_id = self.clean_text(record.external_id)
        if not name or not external_id:
            raise ValueError("Record name and external_id are required")
        location = self.resolve_location(record)
        entity_id = self.canonical_id(
            record.entity_type,
            name,
            location,
            occurrence_at=record.starts_at,
        )
        entity = DiscoveryEntity(
            id=entity_id,
            entity_type=record.entity_type,
            name=name,
            description=self.clean_optional(record.generated_description),
            address=location.address,
            postal_code=location.postal_code,
            latitude=location.latitude,
            longitude=location.longitude,
            quality_score=self.quality_score(location),
        )
        facts = {
            "name": entity.name,
            "address": entity.address,
            "postal_code": entity.postal_code,
            "latitude": entity.latitude,
            "longitude": entity.longitude,
        }
        self.repository.upsert_entity(
            entity,
            SourceRecord(
                source_id=source.id,
                external_id=external_id,
                entity_id=entity_id,
                source_url=record.source_url,
                raw_payload=record.raw_facts,
                fetched_at=self.now,
                verified_at=self.now,
            ),
            [
                FieldProvenance(
                    entity_id=entity_id,
                    field_name=field,
                    source_id=source.id,
                    value=value,
                )
                for field, value in facts.items()
                if value is not None
            ],
        )
        if record.entity_type == EntityType.EVENT:
            self.repository.upsert_event_profile(
                EventProfile(
                    entity_id=entity_id,
                    starts_at=record.starts_at,
                    ends_at=record.ends_at,
                    category=record.category,
                    organiser=record.organiser,
                    ticketed=record.ticketed,
                    price_min=record.price_min,
                    currency=record.currency,
                    booking_url=record.booking_url or record.source_url,
                    source_url=record.source_url or source.base_url or "",
                    source_id=source.id,
                )
            )
        return entity_id

    def resolve_location(self, record: AggregationRecord) -> GeoResolution:
        location = GeoResolution(
            address=self.clean_optional(record.address) or "Singapore",
            postal_code=self.clean_postal_code(record.postal_code),
            latitude=record.latitude,
            longitude=record.longitude,
        )
        needs_geocoding = not location.postal_code or (
            location.latitude is None or location.longitude is None
        )
        if needs_geocoding and self.geocoder and record.address:
            resolved = self.geocoder.resolve(record.address)
            if resolved:
                return resolved
        return location

    @classmethod
    def canonical_id(
        cls,
        entity_type: EntityType,
        name: str,
        location: GeoResolution,
        *,
        occurrence_at: datetime | None = None,
    ) -> str:
        if location.postal_code:
            location_key = f"postal:{location.postal_code}"
        elif location.latitude is not None and location.longitude is not None:
            location_key = f"geo:{location.latitude:.4f},{location.longitude:.4f}"
        else:
            location_key = f"address:{cls.normalise_key(location.address)}"
        occurrence_key = ""
        if entity_type == EntityType.EVENT and occurrence_at is not None:
            occurrence_key = f"|date:{occurrence_at.date().isoformat()}"
        fingerprint = (
            f"{entity_type.value}|{cls.normalise_key(name)}|{location_key}"
            f"{occurrence_key}"
        )
        digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:24]
        return f"{entity_type.value}:canonical:{digest}"

    @staticmethod
    def normalise_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.casefold())

    @staticmethod
    def clean_text(value: str) -> str:
        return " ".join(str(value or "").split())

    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        cleaned = cls.clean_text(value or "")
        return cleaned or None

    @staticmethod
    def clean_postal_code(value: str | None) -> str | None:
        match = re.search(r"\b(\d{6})\b", str(value or ""))
        return match.group(1) if match else None

    @staticmethod
    def quality_score(location: GeoResolution) -> float:
        score = 0.5
        if location.postal_code:
            score += 0.2
        if location.latitude is not None and location.longitude is not None:
            score += 0.2
        return score
