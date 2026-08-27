from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from aug9.core import database
from aug9.discovery.models import DiscoverySource, SourcePermission
from aug9.discovery.repository import DiscoveryRepository


class FoodCandidate(BaseModel):
    id: str
    source_id: str
    external_id: str
    name: str
    address_text: str | None = None
    opening_hours_text: str | None = None
    dish_tags: list[str] = Field(default_factory=list)
    latitude: float = Field(ge=1.1, le=1.5)
    longitude: float = Field(ge=103.6, le=104.1)
    status: str = "staged"
    quarantine_reason: str | None = None


@dataclass(frozen=True)
class FoodCandidateImportSummary:
    run_id: str
    received: int
    staged: int
    quarantined: int
    rejected: int
    duplicates: int


class FoodCandidateRepository:
    def upsert(self, candidate: FoodCandidate) -> None:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"""
            INSERT INTO discovery_food_candidates (
                id, source_id, external_id, name, address_text,
                opening_hours_text, dish_tags, latitude, longitude,
                status, quarantine_reason
            ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
            ON CONFLICT(source_id, external_id) DO UPDATE SET
                name = excluded.name,
                address_text = excluded.address_text,
                opening_hours_text = excluded.opening_hours_text,
                dish_tags = excluded.dish_tags,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                status = excluded.status,
                quarantine_reason = excluded.quarantine_reason,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                candidate.id,
                candidate.source_id,
                candidate.external_id,
                candidate.name,
                candidate.address_text,
                candidate.opening_hours_text,
                json.dumps(candidate.dish_tags),
                candidate.latitude,
                candidate.longitude,
                candidate.status,
                candidate.quarantine_reason,
            ),
        )
        conn.commit()
        conn.close()

    def counts(self, source_id: str) -> dict[str, int]:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"""
            SELECT status, COUNT(*)
            FROM discovery_food_candidates
            WHERE source_id = {p}
            GROUP BY status
            """,
            (source_id,),
        )
        result = dict(cursor.fetchall())
        conn.close()
        return result


class FoodCandidateImporter:
    CLOSED_PATTERN = re.compile(
        r"\b(?:permanently closed|closed down|ceased operations?|"
        r"no longer operating|has closed)\b",
        re.IGNORECASE,
    )

    def __init__(
        self,
        repository: DiscoveryRepository,
        candidate_repository: FoodCandidateRepository,
        source: DiscoverySource,
    ) -> None:
        if source.permission not in {
            SourcePermission.RESEARCH_ONLY,
            SourcePermission.LEGAL_REVIEWED,
        }:
            raise ValueError("Candidate sources must be research_only or legal_reviewed")
        if not source.attribution:
            raise ValueError("Source attribution is required")
        self.repository = repository
        self.candidate_repository = candidate_repository
        self.source = source

    def run(self, path: Path) -> FoodCandidateImportSummary:
        self.repository.register_source(self.source)
        run = self.repository.start_ingestion(self.source.id)
        received = staged = quarantined = rejected = duplicates = 0
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("type") != "FeatureCollection":
                raise ValueError("Food candidate file must be a GeoJSON FeatureCollection")
            features = payload.get("features")
            if not isinstance(features, list):
                raise ValueError("FeatureCollection features must be a list")
            received = len(features)
            seen_external_ids: set[str] = set()
            for feature in features:
                try:
                    candidate = self.normalise(feature)
                    if candidate.external_id in seen_external_ids:
                        duplicates += 1
                        continue
                    seen_external_ids.add(candidate.external_id)
                    self.candidate_repository.upsert(candidate)
                    if candidate.status == "quarantined":
                        quarantined += 1
                    else:
                        staged += 1
                except (KeyError, IndexError, TypeError, ValueError):
                    rejected += 1
            self.repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=staged + quarantined,
                records_rejected=rejected,
            )
            return FoodCandidateImportSummary(
                run.id, received, staged, quarantined, rejected, duplicates
            )
        except Exception as exc:
            self.repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=staged + quarantined,
                records_rejected=rejected,
                error=type(exc).__name__,
            )
            raise

    def normalise(self, feature: dict[str, Any]) -> FoodCandidate:
        if feature.get("geometry", {}).get("type") != "Point":
            raise ValueError("Food candidate geometry must be a Point")
        coordinates = feature["geometry"]["coordinates"]
        longitude = float(coordinates[0])
        latitude = float(coordinates[1])
        properties = feature.get("properties") or {}
        name = str(properties.get("name") or "").strip()
        if not name:
            raise ValueError("Food candidate name is required")
        description = str(properties.get("description") or "")
        external_id = hashlib.sha256(
            f"{name.casefold()}|{latitude:.6f}|{longitude:.6f}".encode()
        ).hexdigest()[:24]
        status = "quarantined" if self.CLOSED_PATTERN.search(description) else "staged"
        return FoodCandidate(
            id=f"candidate:{self.source.id}:{external_id}",
            source_id=self.source.id,
            external_id=external_id,
            name=name,
            address_text=self._section(description, "Address"),
            opening_hours_text=self._section(description, "Opening Hours"),
            dish_tags=self._dish_tags(
                self._section(description, "Shop Recommendations")
            ),
            latitude=latitude,
            longitude=longitude,
            status=status,
            quarantine_reason=("possible_closure" if status == "quarantined" else None),
        )

    @staticmethod
    def _section(description: str, label: str) -> str | None:
        match = re.search(
            rf"{re.escape(label)}:<br>\s*(.*?)(?=<br><br>[^<]+:<br>|$)",
            description,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None
        value = re.sub(r"<br\s*/?>", " ", match.group(1), flags=re.IGNORECASE)
        value = re.sub(r"<[^>]+>", "", value)
        value = " ".join(html.unescape(value).split())
        return value or None

    @staticmethod
    def _dish_tags(value: str | None) -> list[str]:
        if not value:
            return []
        return [
            item.strip()
            for item in re.split(r"[,;/]", value)
            if item.strip()
        ][:12]
