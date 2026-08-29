from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    FieldProvenance,
    SourcePermission,
    SourceRecord,
)
from aug9.discovery.repository import DiscoveryRepository


PLAYGROUND_SOURCE_ID = "singapore_playgrounds_compilation"


@dataclass(frozen=True)
class PlaygroundImportSummary:
    run_id: str
    received: int
    upserted: int
    rejected: int


class PlaygroundGeoJsonImporter:
    def __init__(self, repository: DiscoveryRepository) -> None:
        self.repository = repository

    def run(self, path: str | Path) -> PlaygroundImportSummary:
        self.repository.register_source(
            DiscoverySource(
                id=PLAYGROUND_SOURCE_ID,
                name="Singapore playgrounds compilation",
                permission=SourcePermission.USER_PROVIDED,
                attribution="NParks Playgrounds Directory / PlaySG / OneMap; compiled dataset supplied by Aug9",
            )
        )
        run = self.repository.start_ingestion(PLAYGROUND_SOURCE_ID)
        received = upserted = rejected = 0
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            if payload.get("type") != "FeatureCollection":
                raise ValueError("Playground file must be a GeoJSON FeatureCollection")
            features = payload.get("features")
            if not isinstance(features, list):
                raise ValueError("Playground GeoJSON must contain a feature list")
            received = len(features)
            for feature in features:
                try:
                    entity, record, provenance = self.normalise(feature)
                    self.repository.upsert_entity(entity, record, provenance)
                    upserted += 1
                except (KeyError, TypeError, ValueError):
                    rejected += 1
            self.repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=upserted,
                records_rejected=rejected,
            )
            return PlaygroundImportSummary(run.id, received, upserted, rejected)
        except Exception as exc:
            self.repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=upserted,
                records_rejected=rejected,
                error=type(exc).__name__,
            )
            raise

    @staticmethod
    def normalise(feature: dict[str, Any]):
        geometry = feature["geometry"]
        coordinates = geometry["coordinates"]
        properties = feature["properties"]
        if geometry.get("type") != "Point" or len(coordinates) < 2:
            raise ValueError("Playground feature must contain point coordinates")
        longitude, latitude = float(coordinates[0]), float(coordinates[1])
        if not (1.0 <= latitude <= 1.6 and 103.4 <= longitude <= 104.2):
            raise ValueError("Playground coordinates fall outside Singapore")
        name = str(properties.get("name") or "").strip()
        if not name:
            raise ValueError("Playground feature is missing a name")
        address = str(properties.get("address") or "").strip() or None
        external_id = str(properties.get("id") or feature.get("id") or "").strip()
        if not external_id:
            external_id = hashlib.sha256(
                f"{name.casefold()}|{latitude}|{longitude}".encode()
            ).hexdigest()[:20]
        entity_id = f"playground:{external_id}"
        description = str(
            properties.get("age_suitability_details")
            or properties.get("theme")
            or ""
        ).strip() or None
        entity = DiscoveryEntity(
            id=entity_id,
            entity_type=EntityType.PLAYGROUND,
            name=name,
            description=description,
            address=address,
            latitude=latitude,
            longitude=longitude,
            quality_score=1.0 if address and description else 0.8,
        )
        record = SourceRecord(
            source_id=PLAYGROUND_SOURCE_ID,
            external_id=external_id,
            entity_id=entity_id,
            raw_payload=feature,
        )
        provenance = [
            FieldProvenance(
                entity_id=entity_id,
                field_name=field,
                source_id=PLAYGROUND_SOURCE_ID,
                value=value,
            )
            for field, value in entity.model_dump().items()
            if field not in {"id", "entity_type", "quality_score"} and value is not None
        ]
        return entity, record, provenance
