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
    def __init__(self, listings=None):
        self.calls = []
        self.listings = listings

    def discover(self, **kwargs):
        self.calls.append(kwargs)
        return self.listings if self.listings is not None else [
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


def test_database_provider_ranks_geocoded_events_by_proximity():
    near = DiscoveryEntity(
        id="event:near",
        entity_type=EntityType.EVENT,
        name="Nearby event",
        latitude=1.281,
        longitude=103.845,
    )
    far = DiscoveryEntity(
        id="event:far",
        entity_type=EntityType.EVENT,
        name="Far event",
        latitude=1.35,
        longitude=103.94,
    )
    profile_near = EventProfile(
        entity_id=near.id,
        starts_at=datetime(2030, 8, 23, tzinfo=UTC),
        source_url="https://example.gov.sg/near",
        source_id="official-events",
    )
    profile_far = EventProfile(
        entity_id=far.id,
        starts_at=datetime(2030, 8, 23, tzinfo=UTC),
        source_url="https://example.gov.sg/far",
        source_id="official-events",
    )
    repository = FakeRepository(rows=[(far, profile_far), (near, profile_near)])

    listings = DatabaseEventProvider(repository=repository).discover(
        latitude=1.28,
        longitude=103.844,
    )

    assert [listing.name for listing in listings] == ["Nearby event", "Far event"]
    assert listings[0].distance_km < listings[1].distance_km
    assert repository.calls[0]["limit"] == 50


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


def test_skill_builds_single_day_saturday_window():
    provider = FakeEventProvider()
    SgEventsSkill(provider).execute(
        UserContext(intent="Plan my Saturday in Singapore"), {}
    )

    call = provider.calls[0]
    assert call["starts_after"].weekday() == 5
    assert call["starts_before"] - call["starts_after"] == __import__("datetime").timedelta(days=1)
    assert call["query"] is None


def test_lifeops_shortlist_prioritises_events_starting_in_window():
    now = datetime.now(UTC)
    days_until_saturday = (5 - now.weekday()) % 7
    saturday = (now + __import__("datetime").timedelta(days=days_until_saturday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    listings = [
        EventListing(
            name="Ongoing exhibition",
            starts_at=saturday - __import__("datetime").timedelta(days=10),
            ends_at=saturday,
            source_url="https://example.gov.sg/ongoing",
        ),
        *[
            EventListing(
                name=f"Saturday event {index}",
                starts_at=saturday + __import__("datetime").timedelta(hours=index),
                source_url=f"https://example.gov.sg/{index}",
            )
            for index in range(4)
        ],
    ]

    result = SgEventsSkill(FakeEventProvider(listings=listings)).execute(
        UserContext(intent="Plan my Saturday"), {}
    )

    assert [item["name"] for item in result.data["events"]] == [
        "Saturday event 0",
        "Saturday event 1",
        "Saturday event 2",
    ]
    assert len(result.actions) == 3


def test_lifeops_shortlist_accepts_database_timestamps_without_timezone():
    listing = EventListing(
        name="Saturday event",
        starts_at=datetime(2030, 8, 24),
        source_url="https://example.gov.sg/saturday",
    )

    result = SgEventsSkill(FakeEventProvider(listings=[listing])).execute(
        UserContext(intent="Plan my Saturday"), {}
    )

    assert result.success is True
    assert result.data["events"][0]["name"] == "Saturday event"


def test_skill_offers_attributed_external_guides_when_catalog_is_empty():
    result = SgEventsSkill(FakeEventProvider(listings=[])).execute(
        UserContext(intent="What can I do this weekend?"), {}
    )

    assert result.success is False
    assert [action.label for action in result.actions] == [
        "Browse Honeycombers events",
        "Browse Visit Singapore events",
    ]
    assert all(
        action.metadata["source_access"] == "link_only"
        for action in result.actions
    )
