from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    FieldProvenance,
    FoodProfile,
    OpeningPeriod,
    RelationshipType,
    SourcePermission,
    SourceRecord,
)
from aug9.discovery.repository import DiscoveryRepository


INGESTABLE_PERMISSIONS = {
    SourcePermission.OPEN_DATA,
    SourcePermission.LICENSED_PARTNER,
    SourcePermission.LEGAL_REVIEWED,
}


@dataclass(frozen=True)
class FoodProfileImportSummary:
    run_id: str
    received: int
    upserted: int
    rejected: int


class FoodProfileImporter:
    def __init__(
        self,
        repository: DiscoveryRepository,
        source: DiscoverySource,
    ) -> None:
        if source.permission not in INGESTABLE_PERMISSIONS:
            raise ValueError(
                f"Source permission '{source.permission}' does not allow ingestion"
            )
        if not source.attribution:
            raise ValueError("Source attribution is required")
        self.repository = repository
        self.source = source

    def run(self, path: Path) -> FoodProfileImportSummary:
        self.repository.register_source(self.source)
        run = self.repository.start_ingestion(self.source.id)
        received = upserted = rejected = 0
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    received += 1
                    try:
                        self.ingest_row(row)
                        upserted += 1
                    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                        rejected += 1
            self.repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=upserted,
                records_rejected=rejected,
            )
            return FoodProfileImportSummary(run.id, received, upserted, rejected)
        except Exception as exc:
            self.repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=upserted,
                records_rejected=rejected,
                error=type(exc).__name__,
            )
            raise

    def ingest_row(self, row: dict[str, Any]) -> None:
        external_id = self._required(row, "external_id")
        name = self._required(row, "name")
        parent_entity_id = self._required(row, "parent_entity_id")
        if self.repository.get_entity(parent_entity_id) is None:
            raise ValueError(f"Unknown parent entity: {parent_entity_id}")

        entity_id = f"food:{self.source.id}:{external_id}"
        entity = DiscoveryEntity(
            id=entity_id,
            entity_type=EntityType.FOOD_STALL,
            name=name,
            description=self._optional(row, "description"),
            address=self._optional(row, "address"),
            postal_code=self._optional(row, "postal_code"),
            latitude=self._optional_float(row, "latitude"),
            longitude=self._optional_float(row, "longitude"),
            quality_score=self._quality_score(row),
        )
        profile = FoodProfile(
            entity_id=entity_id,
            venue_kind=self._optional(row, "venue_kind") or "hawker_stall",
            price_min=self._optional_float(row, "price_min"),
            price_max=self._optional_float(row, "price_max"),
            currency=self._optional(row, "currency") or "SGD",
            dietary_attributes=self._list(row, "dietary_attributes"),
            reservation_url=self._optional(row, "reservation_url"),
        )
        tags = {
            category: values
            for category in ("cuisine", "dish")
            if (values := self._list(row, category))
        }
        periods = self._opening_periods(entity_id, row)
        source_url = self._optional(row, "source_url")
        record = SourceRecord(
            source_id=self.source.id,
            external_id=external_id,
            entity_id=entity_id,
            source_url=source_url,
            raw_payload=dict(row),
        )
        provenance = [
            FieldProvenance(
                entity_id=entity_id,
                field_name=field,
                source_id=self.source.id,
                value=value,
            )
            for field, value in {
                "name": name,
                "price_min": profile.price_min,
                "price_max": profile.price_max,
                "dietary_attributes": profile.dietary_attributes,
                "opening_hours": [item.model_dump() for item in periods],
            }.items()
            if value not in (None, [], "")
        ]

        self.repository.upsert_entity(entity, record, provenance)
        self.repository.add_relationship(
            parent_entity_id,
            entity_id,
            RelationshipType.CONTAINS,
            source_id=self.source.id,
        )
        self.repository.upsert_food_profile(
            profile,
            source_id=self.source.id,
            tags=tags,
        )
        self.repository.replace_opening_hours(
            entity_id,
            periods,
            source_id=self.source.id,
        )

    def _opening_periods(
        self,
        entity_id: str,
        row: dict[str, Any],
    ) -> list[OpeningPeriod]:
        raw = self._optional(row, "opening_hours_json")
        if not raw:
            return []
        payload = json.loads(raw)
        if not isinstance(payload, list):
            raise ValueError("opening_hours_json must be a list")
        return [
            OpeningPeriod(
                entity_id=entity_id,
                day_of_week=item["day_of_week"],
                opens_at=item["opens_at"],
                closes_at=item["closes_at"],
                source_id=self.source.id,
            )
            for item in payload
        ]

    @staticmethod
    def _required(row: dict[str, Any], field: str) -> str:
        value = str(row.get(field) or "").strip()
        if not value:
            raise ValueError(f"{field} is required")
        return value

    @staticmethod
    def _optional(row: dict[str, Any], field: str) -> str | None:
        value = str(row.get(field) or "").strip()
        return value or None

    @classmethod
    def _optional_float(cls, row: dict[str, Any], field: str) -> float | None:
        value = cls._optional(row, field)
        return float(value) if value is not None else None

    @classmethod
    def _list(cls, row: dict[str, Any], field: str) -> list[str]:
        value = cls._optional(row, field)
        return [item.strip() for item in value.split("|") if item.strip()] if value else []

    @classmethod
    def _quality_score(cls, row: dict[str, Any]) -> float:
        value = cls._optional_float(row, "quality_score")
        return value if value is not None else 0.8
