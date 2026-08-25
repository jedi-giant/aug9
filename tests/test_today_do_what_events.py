from datetime import UTC, datetime

import httpx

from aug9.discovery.models import SourcePermission
from aug9.discovery.today_do_what_events import TodayDoWhatEventImporter


class FakeRepository:
    def __init__(self):
        self.source = None
        self.entities = []
        self.profiles = []

    def register_source(self, source):
        self.source = source

    def start_ingestion(self, source_id):
        return type("Run", (), {"id": "run-1"})()

    def complete_ingestion(self, run, **kwargs):
        return run

    def upsert_entity(self, entity, record, provenance):
        self.entities.append((entity, record, provenance))

    def upsert_event_profile(self, profile):
        self.profiles.append(profile)


HTML = """
<div class="act card" data-kind="activity"
 data-name="Singapore Design Weekend"
 data-pricelabel="🆓"
 data-location="Bras Basah, Singapore"
 data-dates="28 Aug – 30 Aug"
 data-desc="Publisher description that must not be stored"
 data-moreinfo="https://example.org/design-weekend"></div>
"""


def test_imports_minimal_facts_and_discards_publisher_description():
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=HTML))
    )
    repository = FakeRepository()
    summary = TodayDoWhatEventImporter(
        repository,
        client,
        now=datetime(2026, 8, 26, tzinfo=UTC),
    ).run()

    assert (summary.received, summary.upserted, summary.rejected) == (1, 1, 0)
    assert repository.source.permission == SourcePermission.LEGAL_REVIEWED
    assert repository.source.name == "Source 1"
    assert repository.source.attribution == "Source 1 (todaydowhat.com)"
    entity, record, _ = repository.entities[0]
    assert entity.name == "Singapore Design Weekend"
    assert "Publisher description" not in entity.description
    assert "description" not in record.raw_payload
    assert record.source_url == "https://example.org/design-weekend"
    assert repository.profiles[0].price_min == 0
    assert repository.profiles[0].booking_url == "https://example.org/design-weekend"
    assert repository.profiles[0].source_url == "https://example.org/design-weekend"


def test_rejects_expired_and_non_https_events():
    repository = FakeRepository()
    importer = TodayDoWhatEventImporter(
        repository,
        httpx.Client(),
        now=datetime(2026, 8, 26, tzinfo=UTC),
    )
    expired = {
        "data-name": "Expired",
        "data-location": "Singapore",
        "data-dates": "1 Jan – 2 Jan",
        "data-moreinfo": "https://example.org/expired",
    }
    unsafe = {
        "data-name": "Unsafe",
        "data-location": "Singapore",
        "data-dates": "28 Aug – 30 Aug",
        "data-moreinfo": "http://example.org/unsafe",
    }

    for card in (expired, unsafe):
        try:
            importer.upsert(card)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid card should be rejected")


def test_cross_year_date_range_rolls_end_into_next_year():
    importer = TodayDoWhatEventImporter(
        FakeRepository(),
        httpx.Client(),
        now=datetime(2026, 12, 1, tzinfo=UTC),
    )

    start, end = importer.parse_date_range("15 Dec – 15 Jan")

    assert start.year == 2026
    assert end is not None and end.year == 2027
