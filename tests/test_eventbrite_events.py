import httpx
import pytest

from aug9.discovery.eventbrite_events import EventbriteEventImporter


class FakeRepository:
    def __init__(self):
        self.sources = []
        self.entities = []
        self.profiles = []

    def register_source(self, source):
        self.sources.append(source)

    def start_ingestion(self, source_id):
        return type("Run", (), {"id": "run-1"})()

    def complete_ingestion(self, run, **kwargs):
        return run

    def upsert_entity(self, entity, record, provenance):
        self.entities.append((entity, record, provenance))

    def upsert_event_profile(self, profile):
        self.profiles.append(profile)


def event_payload(event_id="123", country="SG"):
    return {
        "id": event_id,
        "name": {"text": "Singapore Design Weekend"},
        "description": {"text": "A public design programme."},
        "start": {"utc": "2030-08-23T11:00:00Z"},
        "end": {"utc": "2030-08-23T15:00:00Z"},
        "url": f"https://www.eventbrite.sg/e/{event_id}",
        "is_free": True,
        "privacy_setting": "unlocked",
        "venue": {
            "latitude": "1.299",
            "longitude": "103.851",
            "address": {
                "country": country,
                "localized_address_display": "Bras Basah, Singapore",
                "postal_code": "189555",
            },
        },
        "organizer": {"name": "Design Singapore"},
        "category": {"name": "Hobbies"},
    }


def test_importer_discovers_organizations_and_imports_singapore_events():
    def handler(request):
        assert request.headers["Authorization"] == "Bearer private-token"
        if request.url.path.endswith("/users/me/organizations/"):
            return httpx.Response(
                200,
                json={
                    "organizations": [{"id": "org-1"}],
                    "pagination": {"has_more_items": False},
                },
            )
        return httpx.Response(
            200,
            json={
                "events": [event_payload()],
                "pagination": {"has_more_items": False},
            },
        )

    repository = FakeRepository()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    summary = EventbriteEventImporter(
        repository, client, token="private-token"
    ).run()

    assert (summary.received, summary.upserted, summary.rejected) == (1, 1, 0)
    assert repository.entities[0][0].name == "Singapore Design Weekend"
    assert repository.profiles[0].category == "Hobbies"
    assert repository.profiles[0].price_min == 0


def test_importer_rejects_non_singapore_events():
    repository = FakeRepository()
    importer = EventbriteEventImporter(
        repository,
        httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500))),
        token="private-token",
    )

    with pytest.raises(ValueError, match="not located in Singapore"):
        importer.upsert(event_payload(country="US"))


def test_importer_requires_private_token():
    with pytest.raises(ValueError, match="private token"):
        EventbriteEventImporter(FakeRepository(), httpx.Client(), token="")
