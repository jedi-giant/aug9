from datetime import UTC, datetime

import httpx
import pytest

from aug9.core import database
from aug9.discovery.aggregation import DataAggregationEngine
from aug9.discovery.public_events import (
    GovernedHttpClient,
    PublicEventAdapter,
    PublicEventSource,
)
from aug9.discovery.repository import DiscoveryRepository


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "public-events.db")
    database.initialise_database()
    return DiscoveryRepository()


def test_structured_event_is_minimised_and_stored(repository, monkeypatch):
    monkeypatch.setattr("aug9.discovery.public_events.time.sleep", lambda _: None)
    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Event",
     "name":"Public Festival","startDate":"2026-09-01T10:00:00+08:00",
     "endDate":"2026-09-02T18:00:00+08:00",
     "description":"Publisher prose must not be copied",
     "performer":{"@type":"Person","name":"Personal data must not be copied"},
     "location":{"@type":"Place","name":"Example Hall",
       "address":{"streetAddress":"1 Example Road","postalCode":"123456",
       "addressCountry":"SG"}},
     "offers":{"price":"12.50"},"url":"https://events.example/event/1"}
    </script>
    """

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(200, text=html)

    source = PublicEventSource(
        "approved_public_events",
        "Approved Public Events",
        "https://events.example/list",
        ("events.example",),
        ("/event/",),
        max_pages=1,
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = PublicEventAdapter(
        source,
        GovernedHttpClient(client, minimum_interval_seconds=1),
        now=datetime(2026, 8, 26, tzinfo=UTC),
    )

    summary = DataAggregationEngine(repository).run(
        source.discovery_source(), adapter
    )
    entity = repository.search_entities("Public Festival")[0]

    assert (summary.received, summary.upserted, summary.rejected) == (1, 1, 0)
    assert entity.postal_code == "123456"
    assert "Publisher prose" not in entity.description
    assert "Personal data" not in entity.description


def test_robots_denial_blocks_collection(monkeypatch):
    monkeypatch.setattr("aug9.discovery.public_events.time.sleep", lambda _: None)

    def handler(request):
        return httpx.Response(200, text="User-agent: *\nDisallow: /")

    source = PublicEventSource(
        "blocked", "Blocked", "https://blocked.example/events",
        ("blocked.example",), ("/event/",), max_pages=1,
    )
    adapter = PublicEventAdapter(
        source,
        GovernedHttpClient(
            httpx.Client(transport=httpx.MockTransport(handler)),
            minimum_interval_seconds=1,
        ),
    )

    with pytest.raises(ValueError, match="robots policy"):
        adapter.collect()


def test_activity_cards_use_only_factual_fields(monkeypatch):
    monkeypatch.setattr("aug9.discovery.public_events.time.sleep", lambda _: None)
    html = """
    <div data-kind="activity" data-name="Night Market"
      data-location="Marina Bay" data-dates="28 Aug – 30 Aug"
      data-desc="Do not copy this editorial description"
      data-moreinfo="https://activities.example/event/market"></div>
    """

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(200, text=html)

    source = PublicEventSource(
        "activities", "Activities", "https://activities.example/",
        ("activities.example",), ("/event/",), max_pages=1,
    )
    adapter = PublicEventAdapter(
        source,
        GovernedHttpClient(
            httpx.Client(transport=httpx.MockTransport(handler)),
            minimum_interval_seconds=1,
        ),
        now=datetime(2026, 8, 26, tzinfo=UTC),
    )

    record = adapter.parse(adapter.collect()[0])

    assert record.name == "Night Market"
    assert record.starts_at.day == 28
    assert "desc" not in record.raw_facts


def test_visit_singapore_encoded_cards_are_parsed_as_facts():
    html = """
    <div data-cards='[{&#34;cardTitle_t&#34;:&#34;Harbour Festival&#34;,
      &#34;cardDescription_t&#34;:&#34;Publisher prose is excluded&#34;,
      &#34;ctaUrl&#34;:&#34;https://tickets.example/festival&#34;,
      &#34;eventStartDate&#34;:&#34;09-01-2026&#34;,
      &#34;eventEndDate&#34;:&#34;09-03-2026&#34;}]'></div>
    """

    events = PublicEventAdapter._visit_singapore_events(
        html,
        "https://www.visitsingapore.com/whats-happening/all-happenings/",
    )

    assert len(events) == 1
    assert events[0]["name"] == "Harbour Festival"
    assert events[0]["startDate"] == "2026-09-01T00:00:00+00:00"
    assert "description" not in events[0]
