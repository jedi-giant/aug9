import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from aug9.discovery.aggregation import AggregationRecord, DataAggregationEngine
from aug9.discovery.models import DiscoverySource, EntityType, SourcePermission
from aug9.discovery.repository import DiscoveryRepository


USER_AGENT = "Aug9EventIndexer/0.3 (+https://aug-nudge-now.base44.app/)"


@dataclass(frozen=True)
class PublicEventSource:
    id: str
    name: str
    seed_url: str
    allowed_hosts: tuple[str, ...]
    event_path_markers: tuple[str, ...]
    max_pages: int = 5

    def discovery_source(self) -> DiscoverySource:
        return DiscoverySource(
            id=self.id,
            name=self.name,
            permission=SourcePermission.LEGAL_REVIEWED,
            base_url=self.seed_url,
            attribution=self.name,
        )


PUBLIC_EVENT_SOURCES = (
    PublicEventSource(
        "visit_singapore_public", "Visit Singapore",
        "https://www.visitsingapore.com/whats-happening/all-happenings/",
        ("www.visitsingapore.com",), ("/whats-happening/",),
    ),
    PublicEventSource(
        "honeycombers_public", "Honeycombers",
        "https://thehoneycombers.com/singapore/singapore-event-calendar/",
        ("thehoneycombers.com",), ("/singapore/event/",),
    ),
    PublicEventSource(
        "sethlui_public", "SETHLUI.com", "https://sethlui.com/category/events/",
        ("sethlui.com",), ("/events/", "/event/"),
    ),
    PublicEventSource(
        "miss_tam_chiak_public", "Miss Tam Chiak",
        "https://www.misstamchiak.com/", ("www.misstamchiak.com",),
        ("/events/", "/event/"), max_pages=3,
    ),
    PublicEventSource(
        "heritage_sg_public", "HeritageSG",
        "https://www.heritage.sg/sgheritagefest/programmes",
        ("www.heritage.sg",), ("/sgheritagefest/programmes/",),
    ),
    PublicEventSource(
        "daniel_food_diary_public", "DanielFoodDiary.com",
        "https://danielfooddiary.com/", ("danielfooddiary.com",),
        ("/event", "/festival"), max_pages=3,
    ),
    PublicEventSource(
        "ieatishootipost_public", "ieatishootipost",
        "https://ieatishootipost.sg/", ("ieatishootipost.sg",),
        ("/event", "/festival"), max_pages=3,
    ),
    PublicEventSource(
        "eventbrite_public", "Eventbrite",
        "https://www.eventbrite.sg/d/singapore--singapore/events/",
        ("www.eventbrite.sg",), ("/e/",), max_pages=3,
    ),
    PublicEventSource(
        "ticketmaster_public", "Ticketmaster Singapore",
        "https://www.ticketmaster.sg/", ("www.ticketmaster.sg",),
        ("/activity/detail/",),
    ),
    PublicEventSource(
        "peatix_public", "Peatix", "https://peatix.com/search?country=SG",
        ("peatix.com",), ("/event/",),
    ),
    PublicEventSource(
        "sistic_public", "SISTIC", "https://www.sistic.com.sg/events",
        ("www.sistic.com.sg",), ("/events/",),
    ),
    PublicEventSource(
        "today_do_what_public", "Today Do What", "https://todaydowhat.com/",
        ("todaydowhat.com",), ("/event", "/activity"), max_pages=3,
    ),
)

DISABLED_EVENT_SOURCES = {
    "facebook_events": (
        "Requires an approved Facebook API integration; public-page crawling "
        "must not simulate login or bypass access controls."
    ),
}


class StructuredDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.documents: list[object] = []
        self.activity_cards: list[dict[str, str]] = []
        self._json_depth = 0
        self._json_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = {key: value or "" for key, value in attrs}
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
        if tag == "div" and values.get("data-kind") == "activity":
            self.activity_cards.append(values)
        if tag == "script" and values.get("type", "").casefold() == "application/ld+json":
            self._json_depth = 1
            self._json_parts = []

    def handle_endtag(self, tag):
        if tag == "script" and self._json_depth:
            self._json_depth = 0
            try:
                self.documents.append(json.loads("".join(self._json_parts)))
            except json.JSONDecodeError:
                pass

    def handle_data(self, data):
        if self._json_depth:
            self._json_parts.append(data)


class GovernedHttpClient:
    def __init__(
        self,
        client: httpx.Client,
        *,
        minimum_interval_seconds: float = 3.0,
    ) -> None:
        if minimum_interval_seconds < 1:
            raise ValueError("minimum_interval_seconds must be at least 1")
        self.client = client
        self.minimum_interval_seconds = minimum_interval_seconds
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}

    def get_text(self, url: str, allowed_hosts: tuple[str, ...]) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
            raise ValueError("URL is outside the approved HTTPS source boundary")
        self._ensure_allowed(url)
        self._wait(parsed.hostname)
        response = self.client.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        if response.url.host not in allowed_hosts:
            raise ValueError("Redirect left the approved source boundary")
        if len(response.content) > 5_000_000:
            raise ValueError("Source page exceeds the five megabyte limit")
        return response.text

    def _ensure_allowed(self, url: str) -> None:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        robots = self._robots.get(origin)
        if robots is None:
            self._wait(parsed.hostname or "")
            response = self.client.get(
                origin + "/robots.txt", headers={"User-Agent": USER_AGENT}
            )
            if response.url.host != parsed.hostname:
                raise ValueError("Robots redirect left the approved source boundary")
            robots = RobotFileParser()
            if response.status_code < 400:
                robots.parse(response.text.splitlines())
            else:
                robots.parse([])
            self._robots[origin] = robots
        if not robots.can_fetch(USER_AGENT, url):
            raise ValueError("Source robots policy does not allow this page")

    def _wait(self, host: str) -> None:
        elapsed = time.monotonic() - self._last_request.get(host, 0)
        remaining = self.minimum_interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_request[host] = time.monotonic()


class PublicEventAdapter:
    def __init__(
        self,
        source: PublicEventSource,
        http: GovernedHttpClient,
        *,
        now: datetime | None = None,
    ) -> None:
        self.source = source
        self.http = http
        self.now = now or datetime.now(UTC)

    def collect(self) -> list[dict[str, object]]:
        queue = [self.source.seed_url]
        visited: set[str] = set()
        events: list[dict[str, object]] = []
        while queue and len(visited) < self.source.max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            html = self.http.get_text(url, self.source.allowed_hosts)
            parser = StructuredDataParser()
            parser.feed(html)
            for document in parser.documents:
                for event in self._find_events(document):
                    event["_source_url"] = url
                    events.append(event)
            for card in parser.activity_cards:
                try:
                    events.append(self._activity_event(card, url))
                except ValueError:
                    continue
            for link in parser.links:
                candidate = urljoin(url, link).split("#", 1)[0]
                parsed = urlparse(candidate)
                if (
                    parsed.scheme == "https"
                    and parsed.hostname in self.source.allowed_hosts
                    and any(marker in parsed.path for marker in self.source.event_path_markers)
                    and candidate not in visited
                    and candidate not in queue
                ):
                    queue.append(candidate)
        return events

    def parse(self, raw: dict[str, object]) -> AggregationRecord:
        name = self._text(raw.get("name"))
        starts_at = self._datetime(raw.get("startDate"))
        ends_at = self._datetime(raw.get("endDate")) if raw.get("endDate") else None
        if ends_at and ends_at < self.now:
            raise ValueError("Event has expired")
        location = raw.get("location") or {}
        if isinstance(location, list):
            location = location[0] if location else {}
        address = location.get("address") if isinstance(location, dict) else {}
        if isinstance(address, str):
            street = address
            postal_code = None
            country = "SG"
        else:
            address = address or {}
            street = self._text(
                address.get("streetAddress") or address.get("addressLocality")
            )
            postal_code = self._text(address.get("postalCode")) or None
            country = self._text(address.get("addressCountry"))
        if country and country.casefold() not in {"sg", "singapore"}:
            raise ValueError("Event is outside Singapore")
        venue = self._text(location.get("name")) if isinstance(location, dict) else ""
        display_address = ", ".join(item for item in (venue, street) if item) or "Singapore"
        source_url = self._safe_url(raw.get("url") or raw.get("_source_url"))
        offers = raw.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = self._price(offers.get("price")) if isinstance(offers, dict) else None
        external_id = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:32]
        return AggregationRecord(
            external_id=external_id,
            entity_type=EntityType.EVENT,
            name=name,
            address=display_address,
            postal_code=postal_code,
            generated_description=(
                f"{name} is scheduled at {display_address}. "
                "Open the source page to confirm current details and availability."
            ),
            source_url=source_url,
            raw_facts={
                "name": name,
                "start_date": starts_at.isoformat(),
                "end_date": ends_at.isoformat() if ends_at else None,
                "location": display_address,
                "postal_code": postal_code,
                "source_url": source_url,
                "price": price,
            },
            starts_at=starts_at,
            ends_at=ends_at,
            category="event",
            ticketed=True if price and price > 0 else None,
            price_min=price,
            booking_url=source_url,
        )

    @classmethod
    def _find_events(cls, value):
        if isinstance(value, dict):
            event_type = value.get("@type")
            types = event_type if isinstance(event_type, list) else [event_type]
            if "Event" in types:
                yield dict(value)
            for child in value.values():
                yield from cls._find_events(child)
        elif isinstance(value, list):
            for child in value:
                yield from cls._find_events(child)

    def _activity_event(
        self, card: dict[str, str], source_url: str
    ) -> dict[str, object]:
        label = card.get("data-dates", "").replace("—", "–").strip()
        parts = [item.strip() for item in label.removeprefix("From ").split("–")]

        def parse_day_month(value: str, year: int) -> datetime:
            match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3})", value)
            if not match:
                raise ValueError("Unsupported activity date")
            return datetime.strptime(
                f"{match.group(1)} {match.group(2)} {year}", "%d %b %Y"
            ).replace(tzinfo=UTC)

        start = parse_day_month(parts[0], self.now.year)
        end = parse_day_month(parts[-1], start.year) if len(parts) > 1 else None
        if end and end < start:
            end = end.replace(year=end.year + 1)
        if end:
            end = end.replace(hour=23, minute=59, second=59)
        event_url = card.get("data-moreinfo") or card.get("data-website") or source_url
        return {
            "@type": "Event",
            "name": card.get("data-name", ""),
            "startDate": start.isoformat(),
            "endDate": end.isoformat() if end else None,
            "location": {
                "name": card.get("data-location") or card.get("data-location2"),
                "address": {"addressCountry": "SG"},
            },
            "url": event_url,
            "_source_url": source_url,
        }

    @staticmethod
    def _text(value) -> str:
        return " ".join(str(value or "").split())

    @staticmethod
    def _datetime(value) -> datetime:
        raw = str(value or "").strip()
        if not raw:
            raise ValueError("Event start date is required")
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed

    @staticmethod
    def _safe_url(value) -> str:
        url = str(value or "").strip()
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Event URL must be public HTTPS")
        return url

    @staticmethod
    def _price(value) -> float | None:
        try:
            return float(value) if value not in {None, ""} else None
        except (TypeError, ValueError):
            return None


def run_public_event_imports(
    repository: DiscoveryRepository,
    client: httpx.Client,
) -> list[tuple[str, object]]:
    interval = float(os.getenv("PUBLIC_EVENT_MIN_INTERVAL_SECONDS", "3"))
    http = GovernedHttpClient(client, minimum_interval_seconds=interval)
    results = []
    for source in PUBLIC_EVENT_SOURCES:
        adapter = PublicEventAdapter(source, http)
        try:
            summary = DataAggregationEngine(
                repository, max_records=250
            ).run(source.discovery_source(), adapter)
            results.append((source.id, summary))
        except (httpx.HTTPError, ValueError) as exc:
            results.append((source.id, exc))
    return results
