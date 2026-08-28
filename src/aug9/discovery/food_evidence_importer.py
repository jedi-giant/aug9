from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from aug9.discovery.models import (
    CommercialStatus,
    DiscoverySource,
    EvidenceDirection,
    FoodEvidence,
    FoodEvidenceDimension,
    FoodEvidenceType,
    SourcePermission,
)
from aug9.discovery.repository import DiscoveryRepository


ALLOWED_COLUMNS = {
    "external_id",
    "entity_id",
    "dimension",
    "evidence_type",
    "direction",
    "claim_key",
    "value_json",
    "dish_name",
    "confidence",
    "source_url",
    "observed_at",
    "expires_at",
    "commercial_status",
}
REQUIRED_COLUMNS = ALLOWED_COLUMNS - {"dish_name", "expires_at"}
ALLOWED_CLAIMS = {
    "accessibility",
    "ambience",
    "award_or_recognition",
    "consistency",
    "cuisine",
    "dish_speciality",
    "opening_hours",
    "price",
    "queue",
    "service",
}
CLAIM_DIMENSIONS = {
    "accessibility": {
        FoodEvidenceDimension.CONTEXTUAL_FIT,
        FoodEvidenceDimension.EXPERIENCE,
    },
    "ambience": {FoodEvidenceDimension.EXPERIENCE},
    "award_or_recognition": {FoodEvidenceDimension.FOOD_QUALITY},
    "consistency": {
        FoodEvidenceDimension.FOOD_QUALITY,
        FoodEvidenceDimension.RELIABILITY,
    },
    "cuisine": {FoodEvidenceDimension.CONTEXTUAL_FIT},
    "dish_speciality": {FoodEvidenceDimension.FOOD_QUALITY},
    "opening_hours": {FoodEvidenceDimension.RELIABILITY},
    "price": {FoodEvidenceDimension.CONTEXTUAL_FIT},
    "queue": {
        FoodEvidenceDimension.EXPERIENCE,
        FoodEvidenceDimension.RELIABILITY,
    },
    "service": {FoodEvidenceDimension.EXPERIENCE},
}
ALLOWED_EVIDENCE_TYPES = {
    FoodEvidenceType.FACTUAL,
    FoodEvidenceType.EDITORIAL,
}
MAX_VALUE_BYTES = 2_000


@dataclass(frozen=True)
class FoodEvidenceImportSummary:
    run_id: str
    received: int
    upserted: int
    rejected: int


class FoodEvidenceCsvImporter:
    def __init__(
        self,
        repository: DiscoveryRepository,
        source: DiscoverySource,
    ) -> None:
        if source.permission not in {
            SourcePermission.LICENSED_PARTNER,
            SourcePermission.LEGAL_REVIEWED,
        }:
            raise ValueError(
                "Editorial evidence requires a licensed or legally reviewed source"
            )
        if not source.attribution:
            raise ValueError("Source attribution is required")
        self.repository = repository
        self.source = source

    def run(self, path: Path) -> FoodEvidenceImportSummary:
        self.repository.register_source(self.source)
        run = self.repository.start_ingestion(self.source.id)
        received = upserted = rejected = 0
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                self._validate_columns(reader.fieldnames)
                for row in reader:
                    received += 1
                    try:
                        self.repository.upsert_food_evidence(self.parse_row(row))
                        upserted += 1
                    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                        rejected += 1
            self.repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=upserted,
                records_rejected=rejected,
            )
            return FoodEvidenceImportSummary(run.id, received, upserted, rejected)
        except Exception as exc:
            self.repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=upserted,
                records_rejected=rejected,
                error=type(exc).__name__,
            )
            raise

    def parse_row(self, row: dict[str, Any]) -> FoodEvidence:
        external_id = self._required(row, "external_id")
        evidence_type = FoodEvidenceType(self._required(row, "evidence_type"))
        if evidence_type not in ALLOWED_EVIDENCE_TYPES:
            raise ValueError("CSV import only supports factual or editorial evidence")
        claim_key = self._required(row, "claim_key")
        if claim_key not in ALLOWED_CLAIMS:
            raise ValueError(f"Unsupported food evidence claim: {claim_key}")
        dimension = FoodEvidenceDimension(self._required(row, "dimension"))
        if dimension not in CLAIM_DIMENSIONS[claim_key]:
            raise ValueError(
                f"Claim '{claim_key}' cannot be stored as {dimension.value} evidence"
            )
        value = json.loads(self._required(row, "value_json"))
        serialised = json.dumps(value, sort_keys=True, ensure_ascii=False)
        if len(serialised.encode("utf-8")) > MAX_VALUE_BYTES:
            raise ValueError("Food evidence value exceeds the size limit")
        if not isinstance(value, (dict, list, int, float, bool)):
            raise ValueError("Food evidence value must be structured JSON")
        confidence = float(self._required(row, "confidence"))
        confidence_limit = 0.95 if evidence_type is FoodEvidenceType.FACTUAL else 0.85
        if confidence > confidence_limit:
            raise ValueError(
                f"{evidence_type.value} confidence cannot exceed {confidence_limit}"
            )
        source_url = self._required(row, "source_url")
        if urlparse(source_url).scheme != "https":
            raise ValueError("source_url must use HTTPS")
        observed_at = self._datetime(row, "observed_at", required=True)
        expires_at = self._datetime(row, "expires_at", required=False)
        return FoodEvidence(
            id=f"food-evidence:{self.source.id}:{external_id}",
            entity_id=self._required(row, "entity_id"),
            external_id=external_id,
            dimension=dimension,
            evidence_type=evidence_type,
            direction=EvidenceDirection(self._required(row, "direction")),
            claim_key=claim_key,
            value=value,
            dish_name=self._optional(row, "dish_name"),
            confidence=confidence,
            source_id=self.source.id,
            source_url=source_url,
            observed_at=observed_at,
            expires_at=expires_at,
            commercial_status=CommercialStatus(
                self._required(row, "commercial_status")
            ),
        )

    @staticmethod
    def _validate_columns(fieldnames: list[str] | None) -> None:
        columns = set(fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        unsupported = columns - ALLOWED_COLUMNS
        if missing:
            raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
        if unsupported:
            raise ValueError("Unsupported columns: " + ", ".join(sorted(unsupported)))

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
    def _datetime(
        cls,
        row: dict[str, Any],
        field: str,
        *,
        required: bool,
    ) -> datetime | None:
        value = cls._required(row, field) if required else cls._optional(row, field)
        if value is None:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError(f"{field} must include a timezone")
        return parsed
