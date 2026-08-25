from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from aug9.core import database
from aug9.discovery.models import DiscoverySource, SourcePermission
from aug9.discovery.repository import DiscoveryRepository
from aug9.models import LocationSearchResult, SearchStatus
from aug9.sg_place.provider import OneMapProvider


ONEMAP_HOTEL_ADDRESS_SOURCE_ID = "onemap_hotel_addresses"


class AddressProvider(Protocol):
    def authenticate(self) -> str | None: ...
    def search_with_token(self, query: str, token: str) -> LocationSearchResult: ...


@dataclass(frozen=True)
class HotelAddressCandidate:
    entity_id: str
    name: str
    postal_code: str


@dataclass(frozen=True)
class HotelAddressMatch:
    candidate: HotelAddressCandidate
    address: str
    matched_name: str
    matched_postal_code: str | None


@dataclass(frozen=True)
class HotelAddressSummary:
    run_id: str
    received: int
    upserted: int
    rejected: int


class HotelAddressEnricher:
    def __init__(
        self,
        repository: DiscoveryRepository,
        provider: AddressProvider,
        *,
        limit: int = 50,
    ) -> None:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        self.repository = repository
        self.provider = provider
        self.limit = limit

    @classmethod
    def from_environment(cls) -> HotelAddressEnricher:
        return cls(
            DiscoveryRepository(),
            OneMapProvider.from_environment(),
            limit=int(os.getenv("HOTEL_ADDRESS_ENRICHMENT_LIMIT", "50")),
        )

    def run(self) -> HotelAddressSummary:
        self.repository.register_source(
            DiscoverySource(
                id=ONEMAP_HOTEL_ADDRESS_SOURCE_ID,
                name="OneMap hotel address enrichment",
                permission=SourcePermission.OPEN_DATA,
                base_url="https://www.onemap.gov.sg",
                license_name="OneMap Terms of Use",
                attribution="Singapore Land Authority OneMap",
            )
        )
        run = self.repository.start_ingestion(ONEMAP_HOTEL_ADDRESS_SOURCE_ID)
        candidates = self.get_candidates()
        try:
            token = self.provider.authenticate()
            if not token:
                raise RuntimeError("Unable to authenticate with OneMap")
            matches: list[HotelAddressMatch] = []
            rejected = 0
            for candidate in candidates:
                result = self.provider.search_with_token(
                    candidate.postal_code, token
                )
                location = result.location
                if (
                    result.status != SearchStatus.SUCCESS
                    or location is None
                    or not location.address
                    or (
                        location.postal_code
                        and location.postal_code != candidate.postal_code
                    )
                ):
                    rejected += 1
                    continue
                matches.append(
                    HotelAddressMatch(
                        candidate=candidate,
                        address=location.address,
                        matched_name=location.name,
                        matched_postal_code=location.postal_code,
                    )
                )
            self.upsert_batch(matches)
            self.repository.complete_ingestion(
                run,
                records_received=len(candidates),
                records_upserted=len(matches),
                records_rejected=rejected,
            )
            return HotelAddressSummary(
                run.id, len(candidates), len(matches), rejected
            )
        except Exception as exc:
            self.repository.complete_ingestion(
                run,
                records_received=len(candidates),
                records_upserted=0,
                error=type(exc).__name__,
            )
            raise

    def get_candidates(self) -> list[HotelAddressCandidate]:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"""
            SELECT id, name, postal_code
            FROM discovery_entities
            WHERE entity_type = 'hotel'
              AND status = 'active'
              AND (address IS NULL OR address = '')
              AND postal_code IS NOT NULL
              AND postal_code != ''
            ORDER BY name ASC
            LIMIT {p}
            """,
            (self.limit,),
        )
        candidates = [HotelAddressCandidate(*row) for row in cursor.fetchall()]
        conn.close()
        return candidates

    @staticmethod
    def upsert_batch(matches: list[HotelAddressMatch]) -> None:
        if not matches:
            return
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        fetched_at = datetime.now(UTC).isoformat()
        try:
            cursor.executemany(
                f"""
                UPDATE discovery_entities
                SET address = {p}, updated_at = CURRENT_TIMESTAMP
                WHERE id = {p}
                """,
                [(match.address, match.candidate.entity_id) for match in matches],
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
                    fetched_at = excluded.fetched_at
                """,
                [
                    (
                        ONEMAP_HOTEL_ADDRESS_SOURCE_ID,
                        match.candidate.entity_id,
                        match.candidate.entity_id,
                        "https://www.onemap.gov.sg",
                        json.dumps(
                            {
                                "query": match.candidate.postal_code,
                                "matched_name": match.matched_name,
                                "address": match.address,
                                "postal_code": match.matched_postal_code,
                            },
                            sort_keys=True,
                        ),
                        fetched_at,
                        fetched_at,
                    )
                    for match in matches
                ],
            )
            cursor.execute(
                f"""
                SELECT id, external_id FROM discovery_source_records
                WHERE source_id = {p}
                """,
                (ONEMAP_HOTEL_ADDRESS_SOURCE_ID,),
            )
            record_ids = {external_id: row_id for row_id, external_id in cursor}
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
                [
                    (
                        match.candidate.entity_id,
                        "address",
                        ONEMAP_HOTEL_ADDRESS_SOURCE_ID,
                        record_ids[match.candidate.entity_id],
                        json.dumps(match.address),
                    )
                    for match in matches
                ],
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
