from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    FieldProvenance,
    SourcePermission,
    SourceRecord,
)
from aug9.discovery.repository import DiscoveryRepository


NEA_HAWKERS_DATASET_ID = "d_4a086da0a5553be1d89383cd90d07ecd"
NEA_HAWKERS_SOURCE_ID = "nea_hawker_centres"
DATASET_URL = (
    "https://api-open.data.gov.sg/v1/public/api/datasets/"
    f"{NEA_HAWKERS_DATASET_ID}/poll-download"
)


@dataclass(frozen=True)
class ImportSummary:
    run_id: str
    received: int
    upserted: int
    rejected: int


class NeaHawkerImporter:
    def __init__(
        self,
        repository: DiscoveryRepository,
        client: httpx.Client | None = None,
    ) -> None:
        self.repository = repository
        self.client = client or httpx.Client(timeout=30.0, follow_redirects=True)

    def run(self) -> ImportSummary:
        self.repository.register_source(
            DiscoverySource(
                id=NEA_HAWKERS_SOURCE_ID,
                name="NEA Hawker Centres",
                permission=SourcePermission.OPEN_DATA,
                base_url="https://data.gov.sg",
                license_name="Singapore Open Data Licence 1.0",
                attribution="National Environment Agency via data.gov.sg",
            )
        )
        run = self.repository.start_ingestion(NEA_HAWKERS_SOURCE_ID)
        try:
            features = self.fetch_features()
            upserted = 0
            rejected = 0
            for feature in features:
                try:
                    entity, record, provenance = self.normalise(feature)
                    self.repository.upsert_entity(entity, record, provenance)
                    upserted += 1
                except (KeyError, TypeError, ValueError):
                    rejected += 1
            self.repository.complete_ingestion(
                run,
                records_received=len(features),
                records_upserted=upserted,
                records_rejected=rejected,
            )
            return ImportSummary(run.id, len(features), upserted, rejected)
        except Exception as exc:
            self.repository.complete_ingestion(
                run,
                records_received=0,
                records_upserted=0,
                error=type(exc).__name__,
            )
            raise

    def fetch_features(self) -> list[dict[str, Any]]:
        response = self.client.get(DATASET_URL)
        response.raise_for_status()
        download_url = response.json().get("data", {}).get("url")
        self._validate_download_url(download_url)

        download = self.client.get(download_url)
        download.raise_for_status()
        payload = download.json()
        if payload.get("type") != "FeatureCollection":
            raise ValueError("NEA hawker dataset is not a GeoJSON FeatureCollection")
        features = payload.get("features")
        if not isinstance(features, list):
            raise ValueError("NEA hawker dataset does not contain a feature list")
        return features

    @staticmethod
    def _validate_download_url(url: Any) -> None:
        if not isinstance(url, str):
            raise ValueError("data.gov.sg did not return a download URL")
        parsed = urlparse(url)
        allowed_hosts = {
            "s3.ap-southeast-1.amazonaws.com",
            "blobs.data.gov.sg",
        }
        if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
            raise ValueError("data.gov.sg returned an unexpected download URL")

    @staticmethod
    def normalise(
        feature: dict[str, Any],
    ) -> tuple[DiscoveryEntity, SourceRecord, list[FieldProvenance]]:
        properties = feature["properties"]
        geometry = feature["geometry"]
        coordinates = geometry["coordinates"]
        if geometry.get("type") != "Point" or len(coordinates) < 2:
            raise ValueError("Hawker feature must contain point coordinates")

        longitude = float(coordinates[0])
        latitude = float(coordinates[1])
        if not (1.0 <= latitude <= 1.6 and 103.4 <= longitude <= 104.2):
            raise ValueError("Hawker coordinates fall outside Singapore")

        name = str(properties.get("NAME") or "").strip()
        if not name:
            raise ValueError("Hawker feature is missing a name")
        postal_code = str(properties.get("ADDRESSPOSTALCODE") or "").strip() or None
        address = str(properties.get("ADDRESS_MYENV") or "").strip() or None
        external_id = str(properties.get("OBJECTID") or "").strip()
        if not external_id:
            stable_key = f"{name.casefold()}|{postal_code or ''}"
            external_id = hashlib.sha256(stable_key.encode()).hexdigest()[:20]

        entity_id = f"hawker:{external_id}"
        status = str(properties.get("STATUS") or "active").strip().casefold()
        available_fields = [name, address, postal_code, latitude, longitude]
        quality_score = sum(value is not None for value in available_fields) / len(
            available_fields
        )
        entity = DiscoveryEntity(
            id=entity_id,
            entity_type=EntityType.HAWKER_CENTRE,
            name=name,
            address=address,
            postal_code=postal_code,
            latitude=latitude,
            longitude=longitude,
            status="active" if status in {"active", "existing", "operational"} else status,
            quality_score=quality_score,
        )
        record = SourceRecord(
            source_id=NEA_HAWKERS_SOURCE_ID,
            external_id=external_id,
            entity_id=entity_id,
            source_url=(
                "https://data.gov.sg/datasets/"
                f"{NEA_HAWKERS_DATASET_ID}/view"
            ),
            raw_payload=feature,
        )
        provenance = [
            FieldProvenance(
                entity_id=entity_id,
                field_name=field_name,
                source_id=NEA_HAWKERS_SOURCE_ID,
                value=value,
            )
            for field_name, value in entity.model_dump().items()
            if field_name not in {"id", "entity_type", "quality_score"}
            and value is not None
        ]
        return entity, record, provenance
