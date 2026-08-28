from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

from aug9.core import database
from aug9.discovery.hotel_addresses import AddressProvider
from aug9.discovery.models import DiscoverySource, SourcePermission
from aug9.discovery.repository import DiscoveryRepository
from aug9.discovery.sfa_food_establishments import SFA_SOURCE_ID
from aug9.models import LocationSearchResult, SearchStatus
from aug9.sg_place.provider import OneMapProvider


ONEMAP_FOOD_LOCATION_SOURCE_ID = "onemap_food_locations"


@dataclass(frozen=True)
class FoodLocationCandidate:
    entity_id: str
    name: str
    address: str
    postal_code: str | None

    @property
    def query(self) -> str:
        return self.postal_code or self.address


@dataclass(frozen=True)
class FoodLocationMatch:
    candidate: FoodLocationCandidate
    matched_name: str
    matched_address: str | None
    postal_code: str | None
    latitude: float
    longitude: float


@dataclass(frozen=True)
class FoodLocationRejection:
    candidate: FoodLocationCandidate
    reason: str


@dataclass(frozen=True)
class FoodLocationSummary:
    run_id: str
    received: int
    upserted: int
    rejected: int
    unique_queries: int


class FoodLocationEnricher:
    def __init__(
        self,
        repository: DiscoveryRepository,
        provider: AddressProvider,
        *,
        limit: int = 250,
        request_delay_seconds: float = 0.2,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        if request_delay_seconds < 0:
            raise ValueError("request delay cannot be negative")
        self.repository = repository
        self.provider = provider
        self.limit = limit
        self.request_delay_seconds = request_delay_seconds
        self.sleep = sleep

    @classmethod
    def from_environment(cls) -> FoodLocationEnricher:
        return cls(
            DiscoveryRepository(),
            OneMapProvider.from_environment(),
            limit=int(os.getenv("FOOD_LOCATION_ENRICHMENT_LIMIT", "250")),
            request_delay_seconds=float(
                os.getenv("FOOD_LOCATION_REQUEST_DELAY_SECONDS", "0.2")
            ),
        )

    def run(self) -> FoodLocationSummary:
        self.repository.register_source(
            DiscoverySource(
                id=ONEMAP_FOOD_LOCATION_SOURCE_ID,
                name="OneMap food location enrichment",
                permission=SourcePermission.OPEN_DATA,
                base_url="https://www.onemap.gov.sg",
                license_name="OneMap Terms of Use",
                attribution="Singapore Land Authority OneMap",
            )
        )
        run = self.repository.start_ingestion(ONEMAP_FOOD_LOCATION_SOURCE_ID)
        candidates = self.get_candidates()
        try:
            if not candidates:
                self.repository.complete_ingestion(
                    run, records_received=0, records_upserted=0
                )
                return FoodLocationSummary(run.id, 0, 0, 0, 0)
            token = self.provider.authenticate()
            if not token:
                raise RuntimeError("Unable to authenticate with OneMap")

            results: dict[str, LocationSearchResult] = {}
            for candidate in candidates:
                if candidate.query in results:
                    continue
                if results:
                    self.sleep(self.request_delay_seconds)
                results[candidate.query] = self.provider.search_with_token(
                    candidate.query, token
                )

            matches: list[FoodLocationMatch] = []
            rejections: list[FoodLocationRejection] = []
            for candidate in candidates:
                result = results[candidate.query]
                location = result.location
                postal_mismatch = (
                    candidate.postal_code is not None
                    and location is not None
                    and location.postal_code is not None
                    and location.postal_code != candidate.postal_code
                )
                if (
                    result.status != SearchStatus.SUCCESS
                    or location is None
                    or location.latitude is None
                    or location.longitude is None
                    or postal_mismatch
                    or not (1.1 <= location.latitude <= 1.5)
                    or not (103.6 <= location.longitude <= 104.1)
                ):
                    reason = "postal_mismatch" if postal_mismatch else result.status.value
                    rejections.append(FoodLocationRejection(candidate, reason))
                    continue
                matches.append(
                    FoodLocationMatch(
                        candidate=candidate,
                        matched_name=location.name,
                        matched_address=location.address,
                        postal_code=location.postal_code,
                        latitude=location.latitude,
                        longitude=location.longitude,
                    )
                )
            self.upsert_batch(matches, rejections)
            self.repository.complete_ingestion(
                run,
                records_received=len(candidates),
                records_upserted=len(matches),
                records_rejected=len(rejections),
            )
            return FoodLocationSummary(
                run.id, len(candidates), len(matches), len(rejections), len(results)
            )
        except Exception as exc:
            self.repository.complete_ingestion(
                run,
                records_received=len(candidates),
                records_upserted=0,
                error=type(exc).__name__,
            )
            raise

    def get_candidates(self) -> list[FoodLocationCandidate]:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"""
            SELECT e.id, e.name, e.address, e.postal_code
            FROM discovery_entities e
            WHERE e.status = 'active'
              AND e.entity_type IN ('food_venue', 'food_stall')
              AND e.latitude IS NULL
              AND e.longitude IS NULL
              AND e.address IS NOT NULL
              AND TRIM(e.address) != ''
              AND EXISTS (
                  SELECT 1 FROM discovery_source_records sfa
                  WHERE sfa.source_id = {p} AND sfa.entity_id = e.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM discovery_source_records om
                  WHERE om.source_id = {p} AND om.external_id = e.id
              )
            ORDER BY CASE WHEN e.postal_code IS NOT NULL THEN 0 ELSE 1 END,
                     e.postal_code ASC, e.name ASC
            LIMIT {p}
            """,
            (SFA_SOURCE_ID, ONEMAP_FOOD_LOCATION_SOURCE_ID, self.limit),
        )
        candidates = [FoodLocationCandidate(*row) for row in cursor.fetchall()]
        conn.close()
        return candidates

    @staticmethod
    def upsert_batch(
        matches: list[FoodLocationMatch],
        rejections: list[FoodLocationRejection],
    ) -> None:
        if not matches and not rejections:
            return
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        fetched_at = datetime.now(UTC).isoformat()
        try:
            cursor.executemany(
                f"""
                UPDATE discovery_entities
                SET postal_code = COALESCE(postal_code, {p}),
                    latitude = {p}, longitude = {p},
                    quality_score = CASE
                        WHEN quality_score < 0.85 THEN 0.85 ELSE quality_score END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = {p}
                """,
                [
                    (
                        match.postal_code, match.latitude, match.longitude,
                        match.candidate.entity_id,
                    )
                    for match in matches
                ],
            )
            records = []
            for match in matches:
                records.append(
                    (
                        match.candidate.entity_id,
                        {
                            "query": match.candidate.query,
                            "status": "matched",
                            "matched_name": match.matched_name,
                            "matched_address": match.matched_address,
                            "postal_code": match.postal_code,
                            "latitude": match.latitude,
                            "longitude": match.longitude,
                        },
                        fetched_at,
                    )
                )
            for rejection in rejections:
                records.append(
                    (
                        rejection.candidate.entity_id,
                        {
                            "query": rejection.candidate.query,
                            "status": "rejected",
                            "reason": rejection.reason,
                        },
                        None,
                    )
                )
            cursor.executemany(
                f"""
                INSERT INTO discovery_source_records (
                    source_id, external_id, entity_id, source_url,
                    raw_payload, fetched_at, verified_at
                ) VALUES ({p}, {p}, {p}, 'https://www.onemap.gov.sg', {p}, {p}, {p})
                ON CONFLICT(source_id, external_id) DO UPDATE SET
                    entity_id = excluded.entity_id,
                    raw_payload = excluded.raw_payload,
                    fetched_at = excluded.fetched_at,
                    verified_at = excluded.verified_at
                """,
                [
                    (
                        ONEMAP_FOOD_LOCATION_SOURCE_ID, entity_id, entity_id,
                        json.dumps(payload, sort_keys=True), fetched_at, verified_at,
                    )
                    for entity_id, payload, verified_at in records
                ],
            )
            cursor.execute(
                f"""
                SELECT id, external_id FROM discovery_source_records
                WHERE source_id = {p}
                """,
                (ONEMAP_FOOD_LOCATION_SOURCE_ID,),
            )
            record_ids = {external_id: row_id for row_id, external_id in cursor}
            provenance = []
            for match in matches:
                for field_name, value in (
                    ("postal_code", match.postal_code),
                    ("latitude", match.latitude),
                    ("longitude", match.longitude),
                ):
                    if value is not None:
                        provenance.append(
                            (
                                match.candidate.entity_id, field_name,
                                ONEMAP_FOOD_LOCATION_SOURCE_ID,
                                record_ids[match.candidate.entity_id],
                                json.dumps(value),
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
                provenance,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
