from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from aug9.core import database
from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    SourcePermission,
)
from aug9.discovery.repository import DiscoveryRepository


HLB_HOTELS_DATASET_ID = "d_654e22f14e5bb817423f0e0c9ac4f632"
HLB_HOTELS_SOURCE_ID = "hlb_licensed_hotels"
DATASET_URL = (
    "https://api-open.data.gov.sg/v1/public/api/datasets/"
    f"{HLB_HOTELS_DATASET_ID}/poll-download"
)


@dataclass(frozen=True)
class NormalisedHotel:
    entity: DiscoveryEntity
    external_id: str
    raw_payload: dict[str, Any]
    room_count: int | None
    source_updated_at: str | None


@dataclass(frozen=True)
class HotelImportSummary:
    run_id: str
    received: int
    upserted: int
    rejected: int


class HlbHotelImporter:
    def __init__(
        self,
        repository: DiscoveryRepository,
        client: httpx.Client | None = None,
    ) -> None:
        self.repository = repository
        self.client = client or httpx.Client(timeout=60.0, follow_redirects=True)

    def run(self) -> HotelImportSummary:
        self.repository.register_source(
            DiscoverySource(
                id=HLB_HOTELS_SOURCE_ID,
                name="Licensed Hotels",
                permission=SourcePermission.OPEN_DATA,
                base_url="https://data.gov.sg",
                license_name="Singapore Open Data Licence 1.0",
                attribution="Hotels Licensing Board via data.gov.sg",
            )
        )
        run = self.repository.start_ingestion(HLB_HOTELS_SOURCE_ID)
        received = rejected = 0
        try:
            features = self.fetch_features()
            received = len(features)
            hotels: list[NormalisedHotel] = []
            for feature in features:
                try:
                    hotels.append(self.normalise(feature))
                except (KeyError, TypeError, ValueError):
                    rejected += 1
            self.upsert_batch(hotels)
            self.repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=len(hotels),
                records_rejected=rejected,
            )
            return HotelImportSummary(run.id, received, len(hotels), rejected)
        except Exception as exc:
            self.repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=0,
                records_rejected=rejected,
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
            raise ValueError("HLB hotel dataset is not a GeoJSON FeatureCollection")
        features = payload.get("features")
        if not isinstance(features, list):
            raise ValueError("HLB hotel dataset does not contain a feature list")
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
    def normalise(feature: dict[str, Any]) -> NormalisedHotel:
        properties = feature["properties"]
        geometry = feature["geometry"]
        coordinates = geometry["coordinates"]
        if geometry.get("type") != "Point" or len(coordinates) < 2:
            raise ValueError("Hotel feature must contain point coordinates")
        longitude = float(coordinates[0])
        latitude = float(coordinates[1])
        if not (1.0 <= latitude <= 1.6 and 103.4 <= longitude <= 104.2):
            raise ValueError("Hotel coordinates fall outside Singapore")

        name = str(properties.get("NAME") or "").strip()
        if not name:
            raise ValueError("Hotel feature is missing a name")
        postal_code = str(properties.get("POSTALCODE") or "").strip() or None
        external_id = str(properties.get("OBJECTID") or "").strip()
        if not external_id:
            stable_key = f"{name.casefold()}|{postal_code or ''}"
            external_id = hashlib.sha256(stable_key.encode()).hexdigest()[:20]

        room_value = str(properties.get("TOTALROOMS") or "").strip()
        normalised_room_value = room_value.replace(",", "")
        if normalised_room_value and not normalised_room_value.isdigit():
            raise ValueError("Hotel room count must be a whole number")
        room_count = int(normalised_room_value) if normalised_room_value else None
        if room_count is not None and room_count < 0:
            raise ValueError("Hotel room count cannot be negative")
        description = str(properties.get("DESCRIPTION") or "").strip() or None
        entity = DiscoveryEntity(
            id=f"hotel:{external_id}",
            entity_type=EntityType.HOTEL,
            name=name,
            description=description,
            postal_code=postal_code,
            latitude=latitude,
            longitude=longitude,
            status="active",
            quality_score=sum(
                value is not None
                for value in (name, postal_code, latitude, longitude, room_count)
            ) / 5,
        )
        retained_properties = {
            key: value
            for key, value in properties.items()
            if key not in {"KEEPERNAME", "HYPERLINK"}
        }
        return NormalisedHotel(
            entity=entity,
            external_id=external_id,
            raw_payload={
                "type": feature.get("type"),
                "geometry": geometry,
                "properties": retained_properties,
            },
            room_count=room_count,
            source_updated_at=(
                str(properties.get("FMEL_UPD_D") or "").strip() or None
            ),
        )

    @staticmethod
    def upsert_batch(hotels: list[NormalisedHotel]) -> None:
        if not hotels:
            return
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        fetched_at = datetime.now(UTC).isoformat()
        source_url = (
            "https://data.gov.sg/datasets/"
            f"{HLB_HOTELS_DATASET_ID}/view"
        )
        try:
            cursor.executemany(
                f"""
                INSERT INTO discovery_entities (
                    id, entity_type, name, description, address, postal_code,
                    latitude, longitude, status, quality_score
                ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                ON CONFLICT(id) DO UPDATE SET
                    entity_type = excluded.entity_type,
                    name = excluded.name,
                    description = excluded.description,
                    postal_code = excluded.postal_code,
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    status = excluded.status,
                    quality_score = excluded.quality_score,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [
                    (
                        hotel.entity.id, hotel.entity.entity_type.value,
                        hotel.entity.name, hotel.entity.description,
                        hotel.entity.address, hotel.entity.postal_code,
                        hotel.entity.latitude, hotel.entity.longitude,
                        hotel.entity.status, hotel.entity.quality_score,
                    )
                    for hotel in hotels
                ],
            )
            cursor.executemany(
                f"""
                INSERT INTO discovery_source_records (
                    source_id, external_id, entity_id, source_url,
                    raw_payload, fetched_at, verified_at
                ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
                ON CONFLICT(source_id, external_id) DO UPDATE SET
                    entity_id = excluded.entity_id,
                    source_url = excluded.source_url,
                    raw_payload = excluded.raw_payload,
                    fetched_at = excluded.fetched_at
                """,
                [
                    (
                        HLB_HOTELS_SOURCE_ID, hotel.external_id,
                        hotel.entity.id, source_url,
                        json.dumps(hotel.raw_payload, sort_keys=True),
                        fetched_at, None,
                    )
                    for hotel in hotels
                ],
            )
            cursor.execute(
                f"""
                SELECT id, external_id FROM discovery_source_records
                WHERE source_id = {p}
                """,
                (HLB_HOTELS_SOURCE_ID,),
            )
            record_ids = {external_id: row_id for row_id, external_id in cursor}
            provenance_rows = []
            for hotel in hotels:
                for field_name in (
                    "name", "description", "postal_code", "latitude",
                    "longitude", "status",
                ):
                    value = getattr(hotel.entity, field_name)
                    if value is not None:
                        provenance_rows.append(
                            (
                                hotel.entity.id, field_name,
                                HLB_HOTELS_SOURCE_ID,
                                record_ids[hotel.external_id], json.dumps(value),
                            )
                        )
            cursor.executemany(
                f"""
                INSERT INTO discovery_field_provenance (
                    entity_id, field_name, source_id, source_record_id, value
                ) VALUES ({p}, {p}, {p}, {p}, {p})
                ON CONFLICT(entity_id, field_name, source_id) DO UPDATE SET
                    source_record_id = excluded.source_record_id,
                    value = excluded.value,
                    created_at = CURRENT_TIMESTAMP
                """,
                provenance_rows,
            )
            cursor.executemany(
                f"""
                INSERT INTO discovery_hotel_profiles (
                    entity_id, room_count, source_updated_at, source_id
                ) VALUES ({p}, {p}, {p}, {p})
                ON CONFLICT(entity_id) DO UPDATE SET
                    room_count = excluded.room_count,
                    source_updated_at = excluded.source_updated_at,
                    source_id = excluded.source_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [
                    (
                        hotel.entity.id, hotel.room_count,
                        hotel.source_updated_at, HLB_HOTELS_SOURCE_ID,
                    )
                    for hotel in hotels
                ],
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
