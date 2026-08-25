import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    EventProfile,
    FieldProvenance,
    SourcePermission,
    SourceRecord,
)
from aug9.discovery.repository import DiscoveryRepository


API_BASE_URL = "https://www.eventbriteapi.com/v3"
SOURCE_ID = "eventbrite_api"


@dataclass(frozen=True)
class EventbriteImportSummary:
    received: int
    upserted: int
    rejected: int
    run_id: str


class EventbriteEventImporter:
    def __init__(
        self,
        repository: DiscoveryRepository,
        client: httpx.Client,
        *,
        token: str,
    ) -> None:
        if not token.strip():
            raise ValueError("Eventbrite private token is required")
        self.repository = repository
        self.client = client
        self.token = token.strip()

    @classmethod
    def from_environment(
        cls,
        repository: DiscoveryRepository | None = None,
    ) -> "EventbriteEventImporter":
        token = os.getenv("EVENTBRITE_PRIVATE_TOKEN", "")
        return cls(
            repository or DiscoveryRepository(),
            httpx.Client(timeout=30.0),
            token=token,
        )

    def run(self) -> EventbriteImportSummary:
        self.repository.register_source(
            DiscoverySource(
                id=SOURCE_ID,
                name="Eventbrite API",
                permission=SourcePermission.LICENSED_PARTNER,
                base_url="https://www.eventbrite.com/",
                license_name="Eventbrite API Terms of Use",
                attribution="Eventbrite",
            )
        )
        run = self.repository.start_ingestion(SOURCE_ID)
        received = upserted = rejected = 0
        try:
            for organization_id in self.fetch_organization_ids():
                for payload in self.fetch_events(organization_id):
                    received += 1
                    try:
                        self.upsert(payload)
                        upserted += 1
                    except (KeyError, TypeError, ValueError):
                        rejected += 1
            completed = self.repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=upserted,
                records_rejected=rejected,
            )
        except Exception as exc:
            self.repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=upserted,
                records_rejected=rejected,
                error=type(exc).__name__,
            )
            raise
        return EventbriteImportSummary(received, upserted, rejected, completed.id)

    def fetch_organization_ids(self) -> list[str]:
        return [str(item["id"]) for item in self._paginate("/users/me/organizations/", "organizations")]

    def fetch_events(self, organization_id: str) -> list[dict[str, Any]]:
        return list(
            self._paginate(
                f"/organizations/{organization_id}/events/",
                "events",
                params={
                    "status": "live",
                    "time_filter": "current_future",
                    "order_by": "start_asc",
                    "page_size": "50",
                    "expand": "venue,organizer,category",
                },
            )
        )

    def _paginate(self, path: str, key: str, params=None):
        page = 1
        while True:
            response = self.client.get(
                API_BASE_URL + path,
                headers={"Authorization": f"Bearer {self.token}"},
                params={**(params or {}), "page": page},
            )
            response.raise_for_status()
            payload = response.json()
            yield from payload.get(key, [])
            pagination = payload.get("pagination", {})
            if not pagination.get("has_more_items"):
                break
            page += 1

    def upsert(self, payload: dict[str, Any]) -> None:
        if payload.get("privacy_setting") not in {None, "unlocked"}:
            raise ValueError("Private Eventbrite event")
        venue = payload.get("venue") or {}
        address = venue.get("address") or {}
        country = (address.get("country") or "").upper()
        if country != "SG":
            raise ValueError("Event is not located in Singapore")

        external_id = str(payload["id"])
        entity_id = "event:eventbrite:" + hashlib.sha256(
            external_id.encode("utf-8")
        ).hexdigest()[:24]
        name = self._text(payload["name"])
        description = self._text(payload.get("description")) or None
        starts_at = self._datetime(payload["start"])
        ends_at = self._datetime(payload.get("end")) if payload.get("end") else None
        source_url = str(payload["url"])
        latitude = self._float_or_none(venue.get("latitude"))
        longitude = self._float_or_none(venue.get("longitude"))
        entity = DiscoveryEntity(
            id=entity_id,
            entity_type=EntityType.EVENT,
            name=name,
            description=description,
            address=address.get("localized_address_display") or address.get("address_1"),
            postal_code=address.get("postal_code"),
            latitude=latitude,
            longitude=longitude,
            quality_score=0.85,
        )
        safe_payload = {
            "id": external_id,
            "name": payload.get("name"),
            "description": payload.get("description"),
            "start": payload.get("start"),
            "end": payload.get("end"),
            "url": source_url,
            "is_free": payload.get("is_free"),
            "venue": venue,
            "organizer": payload.get("organizer"),
            "category": payload.get("category"),
        }
        record = SourceRecord(
            source_id=SOURCE_ID,
            external_id=external_id,
            entity_id=entity_id,
            source_url=source_url,
            raw_payload=safe_payload,
            verified_at=datetime.now(UTC),
        )
        provenance = [
            FieldProvenance(
                entity_id=entity_id,
                field_name=field_name,
                source_id=SOURCE_ID,
                value=value,
            )
            for field_name, value in {
                "name": name,
                "description": description,
                "address": entity.address,
                "postal_code": entity.postal_code,
                "latitude": latitude,
                "longitude": longitude,
            }.items()
            if value is not None
        ]
        self.repository.upsert_entity(entity, record, provenance)
        category = payload.get("category") or {}
        organizer = payload.get("organizer") or {}
        self.repository.upsert_event_profile(
            EventProfile(
                entity_id=entity_id,
                starts_at=starts_at,
                ends_at=ends_at,
                category=self._text(category.get("name")) or None,
                organiser=self._text(organizer.get("name")) or None,
                ticketed=not bool(payload.get("is_free")),
                price_min=0 if payload.get("is_free") else None,
                booking_url=source_url,
                source_url=source_url,
                source_id=SOURCE_ID,
            )
        )

    @staticmethod
    def _text(value: Any) -> str:
        if isinstance(value, dict):
            value = value.get("text") or value.get("html") or ""
        return str(value or "").strip()

    @staticmethod
    def _datetime(value: dict[str, Any]) -> datetime:
        raw = value.get("utc") or value.get("local")
        if not raw:
            raise ValueError("Event datetime is missing")
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        return float(value) if value not in {None, ""} else None
