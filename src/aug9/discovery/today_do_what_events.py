import hashlib
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

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


SOURCE_ID = "today_do_what"
SOURCE_URL = "https://todaydowhat.com/"
USER_AGENT = "Aug9EventIndexer/0.1 (+https://aug-nudge-now.base44.app/)"
MONTHS = {
    month: index
    for index, month in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
        start=1,
    )
}


@dataclass(frozen=True)
class TodayDoWhatImportSummary:
    received: int
    upserted: int
    rejected: int
    run_id: str


class ActivityCardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "div":
            return
        values = {key: value or "" for key, value in attrs}
        if values.get("data-kind") != "activity":
            return
        self.cards.append(values)


class TodayDoWhatEventImporter:
    def __init__(
        self,
        repository: DiscoveryRepository,
        client: httpx.Client,
        *,
        now: datetime | None = None,
    ) -> None:
        self.repository = repository
        self.client = client
        self.now = now or datetime.now(UTC)

    @classmethod
    def from_environment(
        cls,
        repository: DiscoveryRepository | None = None,
    ) -> "TodayDoWhatEventImporter":
        timeout = float(os.getenv("EVENT_SCRAPER_TIMEOUT_SECONDS", "30"))
        return cls(
            repository or DiscoveryRepository(),
            httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}),
        )

    def run(self) -> TodayDoWhatImportSummary:
        self.repository.register_source(
            DiscoverySource(
                id=SOURCE_ID,
                name="Today Do What",
                permission=SourcePermission.LEGAL_REVIEWED,
                base_url=SOURCE_URL,
                attribution="Today Do What",
            )
        )
        run = self.repository.start_ingestion(SOURCE_ID)
        received = upserted = rejected = 0
        try:
            for card in self.fetch_cards():
                received += 1
                try:
                    self.upsert(card)
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
        return TodayDoWhatImportSummary(received, upserted, rejected, completed.id)

    def fetch_cards(self) -> list[dict[str, str]]:
        response = self.client.get(SOURCE_URL)
        response.raise_for_status()
        parser = ActivityCardParser()
        parser.feed(response.text)
        return parser.cards[:100]

    def upsert(self, card: dict[str, str]) -> None:
        name = card["data-name"].strip()
        location = card["data-location"].strip()
        date_label = card["data-dates"].strip()
        if not name or not location or not date_label:
            raise ValueError("Required event fact is missing")
        starts_at, ends_at = self.parse_date_range(date_label)
        if ends_at and ends_at < self.now:
            raise ValueError("Event has expired")
        event_url = self.safe_url(
            card.get("data-moreinfo") or card.get("data-website")
        )
        fingerprint = "|".join((name.casefold(), date_label.casefold(), location.casefold()))
        external_id = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:32]
        entity_id = f"event:todaydowhat:{external_id}"
        description = self.original_description(name, location, date_label)
        entity = DiscoveryEntity(
            id=entity_id,
            entity_type=EntityType.EVENT,
            name=name,
            description=description,
            address=location,
            quality_score=0.7,
        )
        record = SourceRecord(
            source_id=SOURCE_ID,
            external_id=external_id,
            entity_id=entity_id,
            source_url=event_url,
            raw_payload={
                "name": name,
                "location": location,
                "date_label": date_label,
                "price_label": card.get("data-pricelabel", ""),
                "event_url": event_url,
            },
            verified_at=self.now,
        )
        self.repository.upsert_entity(
            entity,
            record,
            [
                FieldProvenance(
                    entity_id=entity_id,
                    field_name=field,
                    source_id=SOURCE_ID,
                    value=value,
                )
                for field, value in {
                    "name": name,
                    "address": location,
                }.items()
            ],
        )
        price_label = card.get("data-pricelabel", "").strip()
        is_free = "🆓" in price_label or price_label.casefold() == "free"
        self.repository.upsert_event_profile(
            EventProfile(
                entity_id=entity_id,
                starts_at=starts_at,
                ends_at=ends_at,
                category="activity",
                ticketed=False if is_free else None,
                price_min=0 if is_free else self.price_min(price_label),
                booking_url=event_url,
                source_url=event_url,
                source_id=SOURCE_ID,
            )
        )

    def parse_date_range(self, label: str) -> tuple[datetime, datetime | None]:
        normalized = label.replace("—", "–").strip()
        if normalized.casefold().startswith("from "):
            return self.parse_day_month(normalized[5:]), None
        parts = [part.strip() for part in normalized.split("–")]
        if len(parts) == 1:
            return self.parse_day_month(parts[0]), None
        if len(parts) != 2:
            raise ValueError("Unsupported event date range")
        start = self.parse_day_month(parts[0])
        end = self.parse_day_month(parts[1], year=start.year)
        if end < start:
            end = end.replace(year=end.year + 1)
        return start, end.replace(hour=23, minute=59, second=59)

    def parse_day_month(self, value: str, *, year: int | None = None) -> datetime:
        match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3})", value.strip())
        if not match or match.group(2).title() not in MONTHS:
            raise ValueError("Unsupported event date")
        return datetime(
            year or self.now.year,
            MONTHS[match.group(2).title()],
            int(match.group(1)),
            tzinfo=UTC,
        )

    @staticmethod
    def safe_url(value: Any) -> str:
        url = str(value or "").strip()
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Event URL must be public HTTPS")
        return url

    @staticmethod
    def price_min(label: str) -> float | None:
        match = re.search(r"\$(\d+(?:\.\d+)?)", label)
        return float(match.group(1)) if match else None

    @staticmethod
    def original_description(name: str, location: str, date_label: str) -> str:
        return (
            f"{name} is listed at {location} for {date_label}. "
            "Open the event page to confirm current details and availability."
        )
