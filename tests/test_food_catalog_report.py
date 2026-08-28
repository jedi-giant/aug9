from datetime import UTC, datetime

import pytest

from aug9.core import database
from aug9.discovery.food_catalog_report import build_food_catalog_report
from aug9.discovery.food_locations import FoodLocationEnricher
from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    SourcePermission,
    SourceRecord,
)
from aug9.discovery.repository import DiscoveryRepository
from aug9.discovery.sfa_food_establishments import SFA_SOURCE_ID
from aug9.models import LocationSearchResult, SearchStatus


class NoResultProvider:
    def authenticate(self):
        return "token"

    def search_with_token(self, query, token):
        return LocationSearchResult(status=SearchStatus.NO_RESULTS)


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "food-report.db")
    database.initialise_database()
    repository = DiscoveryRepository()
    repository.register_source(
        DiscoverySource(
            id=SFA_SOURCE_ID,
            name="SFA food establishments",
            permission=SourcePermission.OPEN_DATA,
        )
    )
    return repository


def test_food_catalog_report_summarises_sfa_and_location_coverage(repository):
    repository.upsert_entity(
        DiscoveryEntity(
            id="food:1",
            entity_type=EntityType.FOOD_STALL,
            name="Stall One",
            address="1 Example Street Singapore 123456",
            postal_code="123456",
        ),
        SourceRecord(
            source_id=SFA_SOURCE_ID,
            external_id="licence-1",
            entity_id="food:1",
        ),
        [],
    )
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO discovery_food_profiles "
        "(entity_id, venue_kind, currency, dietary_attributes, source_id) "
        "VALUES (?, 'hawker_stall', 'SGD', '[]', ?)",
        ("food:1", SFA_SOURCE_ID),
    )
    cursor.execute(
        "INSERT INTO discovery_food_safety_profiles "
        "(entity_id, licence_number, safe_grade, business_type, source_id, observed_at) "
        "VALUES (?, 'licence-1', 'A', 'NEA Managed Foodstall', ?, ?)",
        ("food:1", SFA_SOURCE_ID, datetime(2026, 8, 28, tzinfo=UTC).isoformat()),
    )
    conn.commit()
    conn.close()

    FoodLocationEnricher(
        repository, NoResultProvider(), request_delay_seconds=0
    ).run()
    report = build_food_catalog_report(
        now=datetime(2026, 8, 28, tzinfo=UTC)
    )

    assert report.active_food_establishments == 1
    assert report.establishments_by_kind == {"hawker_stall": 1}
    assert report.establishments_by_safe_grade == {"A": 1}
    assert report.missing_postal_code == 0
    assert report.missing_coordinates == 1
    assert report.one_map_attempted == 1
    assert report.one_map_matched == 0
    assert report.one_map_rejected == 1
