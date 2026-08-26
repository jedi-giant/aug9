from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime

from aug9.core import database
from aug9.discovery.hotel_addresses import AddressProvider
from aug9.discovery.models import DiscoverySource, SourcePermission
from aug9.discovery.repository import DiscoveryRepository
from aug9.models import SearchStatus
from aug9.sg_place.provider import OneMapProvider


ONEMAP_EVENT_VENUE_SOURCE_ID = "onemap_event_venues"
GENERIC_VENUES = {
    "online",
    "singapore",
    "various locations",
    "various venues",
    "multiple locations",
    "to be announced",
    "tba",
}


@dataclass(frozen=True)
class EventVenueCandidate:
    entity_id: str
    name: str
    address: str


@dataclass(frozen=True)
class EventVenueMatch:
    candidate: EventVenueCandidate
    matched_name: str
    matched_address: str | None
    postal_code: str | None
    latitude: float
    longitude: float


@dataclass(frozen=True)
class EventVenueSummary:
    run_id: str
    received: int
    upserted: int
    rejected: int


class EventVenueEnricher:
    def __init__(
        self,
        repository: DiscoveryRepository,
        provider: AddressProvider,
        *,
        limit: int = 25,
    ) -> None:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        self.repository = repository
        self.provider = provider
        self.limit = limit

    @classmethod
    def from_environment(cls) -> EventVenueEnricher:
        return cls(
            DiscoveryRepository(),
            OneMapProvider.from_environment(),
            limit=int(os.getenv("EVENT_VENUE_ENRICHMENT_LIMIT", "25")),
        )

    def run(self) -> EventVenueSummary:
        self.repository.register_source(
            DiscoverySource(
                id=ONEMAP_EVENT_VENUE_SOURCE_ID,
                name="OneMap event venue enrichment",
                permission=SourcePermission.OPEN_DATA,
                base_url="https://www.onemap.gov.sg",
                license_name="OneMap Terms of Use",
                attribution="Singapore Land Authority OneMap",
            )
        )
        run = self.repository.start_ingestion(ONEMAP_EVENT_VENUE_SOURCE_ID)
        candidates = self.get_candidates()
        try:
            if not candidates:
                self.repository.complete_ingestion(run)
                return EventVenueSummary(run.id, 0, 0, 0)
            token = self.provider.authenticate()
            if not token:
                raise RuntimeError("Unable to authenticate with OneMap")
            matches: list[EventVenueMatch] = []
            rejected = 0
            for candidate in candidates:
                result = self.provider.search_with_token(candidate.address, token)
                location = result.location
                if (
                    result.status != SearchStatus.SUCCESS
                    or location is None
                    or location.latitude is None
                    or location.longitude is None
                    or not (1.1 <= location.latitude <= 1.5)
                    or not (103.6 <= location.longitude <= 104.1)
                ):
                    rejected += 1
                    continue
                matches.append(
                    EventVenueMatch(
                        candidate=candidate,
                        matched_name=location.name,
                        matched_address=location.address,
                        postal_code=location.postal_code,
                        latitude=location.latitude,
                        longitude=location.longitude,
                    )
                )
            self.upsert_batch(matches)
            self.repository.complete_ingestion(
                run,
                records_received=len(candidates),
                records_upserted=len(matches),
                records_rejected=rejected,
            )
            return EventVenueSummary(run.id, len(candidates), len(matches), rejected)
        except Exception as exc:
            self.repository.complete_ingestion(run, error=type(exc).__name__)
            raise

    def get_candidates(self) -> list[EventVenueCandidate]:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        generic = sorted(GENERIC_VENUES)
        generic_placeholders = ", ".join([p] * len(generic))
        cursor.execute(
            f"""
            SELECT id, name, address
            FROM discovery_entities
            WHERE entity_type = 'event'
              AND status = 'active'
              AND latitude IS NULL
              AND longitude IS NULL
              AND address IS NOT NULL
              AND TRIM(address) != ''
              AND LOWER(TRIM(address)) NOT IN ({generic_placeholders})
            ORDER BY updated_at DESC, name ASC
            LIMIT {p}
            """,
            (*generic, self.limit),
        )
        candidates = [EventVenueCandidate(*row) for row in cursor.fetchall()]
        conn.close()
        return candidates

    @staticmethod
    def upsert_batch(matches: list[EventVenueMatch]) -> None:
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
                SET postal_code = COALESCE(postal_code, {p}),
                    latitude = {p}, longitude = {p},
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = {p}
                """,
                [
                    (
                        match.postal_code,
                        match.latitude,
                        match.longitude,
                        match.candidate.entity_id,
                    )
                    for match in matches
                ],
            )
            for match in matches:
                raw_payload = json.dumps(
                    {
                        "query": match.candidate.address,
                        "matched_name": match.matched_name,
                        "matched_address": match.matched_address,
                        "postal_code": match.postal_code,
                        "latitude": match.latitude,
                        "longitude": match.longitude,
                    },
                    sort_keys=True,
                )
                cursor.execute(
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
                    (
                        ONEMAP_EVENT_VENUE_SOURCE_ID,
                        match.candidate.entity_id,
                        match.candidate.entity_id,
                        "https://www.onemap.gov.sg",
                        raw_payload,
                        fetched_at,
                        fetched_at,
                    ),
                )
                cursor.execute(
                    f"""
                    SELECT id FROM discovery_source_records
                    WHERE source_id = {p} AND external_id = {p}
                    """,
                    (ONEMAP_EVENT_VENUE_SOURCE_ID, match.candidate.entity_id),
                )
                source_record_id = cursor.fetchone()[0]
                for field_name, value in (
                    ("postal_code", match.postal_code),
                    ("latitude", match.latitude),
                    ("longitude", match.longitude),
                ):
                    if value is None:
                        continue
                    cursor.execute(
                        f"""
                        INSERT INTO discovery_field_provenance (
                            entity_id, field_name, source_id, source_record_id, value
                        ) VALUES ({p}, {p}, {p}, {p}, {p})
                        ON CONFLICT(entity_id, field_name, source_id) DO UPDATE SET
                            source_record_id = excluded.source_record_id,
                            value = excluded.value,
                            created_at = CURRENT_TIMESTAMP
                        """,
                        (
                            match.candidate.entity_id,
                            field_name,
                            ONEMAP_EVENT_VENUE_SOURCE_ID,
                            source_record_id,
                            json.dumps(value),
                        ),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
