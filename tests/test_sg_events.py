import sqlite3
from datetime import UTC, datetime

from aug9.core.context import UserContext
from aug9.discovery.models import DiscoveryEntity, EntityType, EventProfile
from aug9.sg_events import DatabaseEventProvider, EventListing, SgEventsSkill


class FakeRepository:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error
        self.calls = []

    def search_events(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.rows


class FakeEventProvider:
    def __init__(self):
        self.calls = []

    def discover(self, **kwargs):
        self.calls.append(kwargs)
        return [
            EventListing(
                name="Singapore Night Festival",
                starts_at=datetime(2030, 8, 23, tzinfo=UTC),
                category="festival",
                source_url="https://example.gov.sg/night-festival",
            )
        ]


def test_database_provider_returns_governed_events():
    entity = DiscoveryEntity(
        id="event:night-festival",
        entity_type=EntityType.EVENT,
        name="Singapore Night Festival",
        address="Bras Basah",
    )
    profile = EventProfile(
        entity_id=entity.id,
        starts_at=datetime(2030, 8, 23, tzinfo=UTC),
        source_url="https://example.gov.sg/night-festival",
        source_id="official-events",
    )
    repository = FakeRepository(rows=[(entity, profile)])

    listings = DatabaseEventProvider(repository=repository).discover(query="Bras Basah")

    assert listings[0].name == "Singapore Night Festival"
    assert repository.calls[0]["query"] == "Bras Basah"


def test_database_provider_handles_database_failure():
    provider = DatabaseEventProvider(
        repository=FakeRepository(error=sqlite3.OperationalError("unavailable"))
    )

    assert provider.discover() == []


def test_skill_returns_structured_events_and_official_action():
    result = SgEventsSkill(FakeEventProvider()).execute(
        UserContext(intent="What events are on?"), {}
    )

    assert result.success is True
    assert result.data["events"][0]["name"] == "Singapore Night Festival"
    assert result.actions[0].metadata["capability"] == "events"
    assert result.actions[0].url == "https://example.gov.sg/night-festival"


def test_skill_builds_weekend_window():
    provider = FakeEventProvider()
    SgEventsSkill(provider).execute(
        UserContext(intent="What can I do this weekend?"),
        {"location": "Bras Basah", "category": "festival"},
    )

    call = provider.calls[0]
    assert call["query"] == "Bras Basah"
    assert call["category"] == "festival"
    assert call["starts_before"] - call["starts_after"] == __import__("datetime").timedelta(days=2)
