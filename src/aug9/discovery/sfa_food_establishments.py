from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

import httpx

from aug9.core import database
from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    SourcePermission,
)
from aug9.discovery.repository import DiscoveryRepository


SFA_SOURCE_ID = "sfa_food_establishments"
SFA_TRACK_RECORD_URL = "https://www.sfa.gov.sg/api/TrackRecord/GetTrackRecord"
SFA_TRACK_RECORD_PAGE = "https://www.sfa.gov.sg/tools-and-resources/track-records"
DEFAULT_BUSINESS_TYPES = (
    "Restaurant",
    "NEA Managed Foodstall",
    "WITHIN A COFFEESHOP/CANTEEN/FOODCOURT",
)
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
POSTAL_CODE_PATTERN = re.compile(r"\bSingapore\s+(\d{6})\b", re.IGNORECASE)


@dataclass(frozen=True)
class NormalisedFoodEstablishment:
    entity: DiscoveryEntity
    external_id: str
    licence_number: str
    venue_kind: str
    safe_grade: str
    business_type: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class SfaFoodImportSummary:
    run_id: str
    received: int
    upserted: int
    rejected: int


class SfaFoodEstablishmentImporter:
    def __init__(
        self,
        repository: DiscoveryRepository,
        client: httpx.Client | None = None,
        *,
        business_types: tuple[str, ...] = DEFAULT_BUSINESS_TYPES,
        request_delay_seconds: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not business_types:
            raise ValueError("At least one SFA food business type is required")
        if request_delay_seconds < 0:
            raise ValueError("SFA request delay cannot be negative")
        self.repository = repository
        self.client = client or httpx.Client(timeout=90.0, follow_redirects=False)
        self.business_types = business_types
        self.request_delay_seconds = request_delay_seconds
        self.sleep = sleep

    def run(self) -> SfaFoodImportSummary:
        self.repository.register_source(
            DiscoverySource(
                id=SFA_SOURCE_ID,
                name="SFA licensed food establishments",
                permission=SourcePermission.OPEN_DATA,
                base_url="https://www.sfa.gov.sg",
                license_name="Singapore Open Data Licence 1.0",
                attribution="Singapore Food Agency",
            )
        )
        run = self.repository.start_ingestion(SFA_SOURCE_ID)
        received = rejected = 0
        try:
            records = self.fetch_records()
            received = len(records)
            establishments: dict[str, NormalisedFoodEstablishment] = {}
            for record in records:
                try:
                    item = self.normalise(record)
                    establishments[item.licence_number] = item
                except (KeyError, TypeError, ValueError):
                    rejected += 1
            self.upsert_batch(list(establishments.values()))
            self.repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=len(establishments),
                records_rejected=rejected,
            )
            return SfaFoodImportSummary(
                run.id, received, len(establishments), rejected
            )
        except Exception as exc:
            self.repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=0,
                records_rejected=rejected,
                error=type(exc).__name__,
            )
            raise

    def fetch_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for index, business_type in enumerate(self.business_types):
            if index:
                self.sleep(self.request_delay_seconds)
            response = self.client.get(
                SFA_TRACK_RECORD_URL,
                params={
                    "postalCode": "",
                    "establishmentAddress": "",
                    "licenceNumber": "",
                    "businessName": "",
                    "licenseeName": "",
                    "typeOfFoodBussiness": business_type,
                    "isShowLicenceSuspended": "false",
                    "grades": "",
                },
                headers={"Accept": "application/json", "User-Agent": "Aug9/0.1"},
            )
            response.raise_for_status()
            if len(response.content) > MAX_RESPONSE_BYTES:
                raise ValueError("SFA response exceeds the configured size limit")
            payload = response.json()
            items = payload.get("data")
            if not isinstance(items, list):
                raise ValueError("SFA response does not contain a data list")
            records.extend(item for item in items if isinstance(item, dict))
        return records

    @staticmethod
    def normalise(record: dict[str, Any]) -> NormalisedFoodEstablishment:
        licence_number = str(record.get("licenceNumber") or "").strip()
        business_name = str(record.get("businessName") or "").strip()
        address = str(record.get("establishmentAddress") or "").strip()
        business_type = str(record.get("typeOfFoodBussiness") or "").strip()
        safe_grade = str(record.get("grades") or "").strip()
        if not licence_number or not address or not business_type or not safe_grade:
            raise ValueError("SFA record is missing required fields")
        if not business_name or business_name.casefold() in {"na", "n/a", "-"}:
            raise ValueError("SFA record has no consumer-facing business name")
        if safe_grade.casefold() not in {"a", "b", "c", "new"}:
            raise ValueError("SFA record contains an unsupported SAFE grade")

        restaurant = "restaurant" in business_type.casefold()
        nea_stall = business_type.casefold() == "nea managed foodstall"
        entity_type = EntityType.FOOD_VENUE if restaurant else EntityType.FOOD_STALL
        venue_kind = (
            "restaurant" if restaurant
            else "hawker_stall" if nea_stall
            else "food_court_stall"
        )
        postal_match = POSTAL_CODE_PATTERN.search(address)
        postal_code = postal_match.group(1) if postal_match else None
        external_hash = hashlib.sha256(licence_number.encode()).hexdigest()[:24]
        entity = DiscoveryEntity(
            id=f"food:sfa:{external_hash}",
            entity_type=entity_type,
            name=business_name,
            address=address,
            postal_code=postal_code,
            status="active",
            quality_score=0.75 if postal_code else 0.65,
        )
        return NormalisedFoodEstablishment(
            entity=entity,
            external_id=licence_number,
            licence_number=licence_number,
            venue_kind=venue_kind,
            safe_grade=safe_grade.title(),
            business_type=business_type,
            raw_payload={
                "refNo": record.get("refNo"),
                "applType": record.get("applType"),
                "establishmentAddress": address,
                "licenceNumber": licence_number,
                "businessName": business_name,
                "typeOfFoodBussiness": business_type,
                "grades": safe_grade,
            },
        )

    @staticmethod
    def upsert_batch(establishments: list[NormalisedFoodEstablishment]) -> None:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        observed_at = datetime.now(UTC).isoformat()
        try:
            cursor.executemany(
                f"""
                INSERT INTO discovery_entities (
                    id, entity_type, name, address, postal_code, status, quality_score
                ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
                ON CONFLICT(id) DO UPDATE SET
                    entity_type = excluded.entity_type,
                    name = excluded.name,
                    address = excluded.address,
                    postal_code = excluded.postal_code,
                    status = excluded.status,
                    quality_score = excluded.quality_score,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [
                    (
                        item.entity.id, item.entity.entity_type.value,
                        item.entity.name, item.entity.address,
                        item.entity.postal_code, item.entity.status,
                        item.entity.quality_score,
                    )
                    for item in establishments
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
                    raw_payload = excluded.raw_payload,
                    fetched_at = excluded.fetched_at,
                    verified_at = excluded.verified_at
                """,
                [
                    (
                        SFA_SOURCE_ID, item.external_id, item.entity.id,
                        SFA_TRACK_RECORD_PAGE,
                        json.dumps(item.raw_payload, sort_keys=True),
                        observed_at, observed_at,
                    )
                    for item in establishments
                ],
            )
            cursor.executemany(
                f"""
                INSERT INTO discovery_food_profiles (
                    entity_id, venue_kind, currency, dietary_attributes, source_id
                ) VALUES ({p}, {p}, 'SGD', '[]', {p})
                ON CONFLICT(entity_id) DO UPDATE SET
                    venue_kind = excluded.venue_kind,
                    source_id = excluded.source_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [
                    (item.entity.id, item.venue_kind, SFA_SOURCE_ID)
                    for item in establishments
                ],
            )
            cursor.executemany(
                f"""
                INSERT INTO discovery_food_safety_profiles (
                    entity_id, licence_number, safe_grade, business_type,
                    source_id, observed_at
                ) VALUES ({p}, {p}, {p}, {p}, {p}, {p})
                ON CONFLICT(entity_id) DO UPDATE SET
                    licence_number = excluded.licence_number,
                    safe_grade = excluded.safe_grade,
                    business_type = excluded.business_type,
                    source_id = excluded.source_id,
                    observed_at = excluded.observed_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [
                    (
                        item.entity.id, item.licence_number, item.safe_grade,
                        item.business_type, SFA_SOURCE_ID, observed_at,
                    )
                    for item in establishments
                ],
            )
            cursor.execute(
                f"""
                UPDATE discovery_entities
                SET status = 'archived', updated_at = CURRENT_TIMESTAMP
                WHERE id IN (
                    SELECT entity_id FROM discovery_source_records
                    WHERE source_id = {p} AND fetched_at <> {p}
                )
                """,
                (SFA_SOURCE_ID, observed_at),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
