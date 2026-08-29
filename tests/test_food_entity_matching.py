from datetime import UTC, datetime

import pytest

from aug9.core import database
from aug9.discovery.food_entity_matching import FoodEntityMatcher
from aug9.discovery.models import DiscoverySource, SourcePermission
from aug9.discovery.repository import DiscoveryRepository
from aug9.discovery.sfa_food_establishments import SFA_SOURCE_ID


@pytest.fixture
def matching_database(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "matching.db")
    database.initialise_database()
    repository = DiscoveryRepository()
    for source in (
        DiscoverySource(
            id=SFA_SOURCE_ID,
            name="SFA",
            permission=SourcePermission.OPEN_DATA,
        ),
        DiscoverySource(
            id="owner_food",
            name="Owner food",
            permission=SourcePermission.USER_PROVIDED,
            attribution="Owner",
        ),
    ):
        repository.register_source(source)
    return repository


def add_entity(entity_id, name, postal_code, latitude, source_id):
    conn = database.get_connection()
    cursor = conn.cursor()
    now = datetime.now(UTC).isoformat()
    cursor.execute(
        "INSERT INTO discovery_entities "
        "(id, entity_type, name, address, postal_code, latitude, longitude, status) "
        "VALUES (?, 'food_venue', ?, 'Example Street', ?, ?, 103.8, 'active')",
        (entity_id, name, postal_code, latitude),
    )
    cursor.execute(
        "INSERT INTO discovery_source_records "
        "(source_id, external_id, entity_id, raw_payload, fetched_at) "
        "VALUES (?, ?, ?, '{}', ?)",
        (source_id, entity_id, entity_id, now),
    )
    conn.commit()
    conn.close()


def test_matcher_applies_only_high_confidence_identity_links(matching_database):
    add_entity("food:sfa:one", "Example Noodles", "123456", 1.3, SFA_SOURCE_ID)
    add_entity(
        "food:owner_food:one", "Example Noodles", "123456", 1.3001, "owner_food"
    )
    add_entity(
        "food:owner_food:other", "Different Restaurant", "654321", 1.4, "owner_food"
    )

    report = FoodEntityMatcher(source_ids=("owner_food",)).run(apply=True)

    assert report["outcomes"] == {"matched": 1, "unmatched": 1}
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT parent_entity_id, child_entity_id FROM discovery_entity_relationships "
        "WHERE relationship_type = 'same_as'"
    )
    assert cursor.fetchall() == [("food:sfa:one", "food:owner_food:one")]
    conn.close()


def test_matcher_quarantines_ambiguous_candidates(matching_database):
    add_entity("food:sfa:a", "Shared Kitchen", "123456", 1.3, SFA_SOURCE_ID)
    add_entity("food:sfa:b", "Shared Kitchen", "123456", 1.3001, SFA_SOURCE_ID)
    add_entity(
        "food:owner_food:shared", "Shared Kitchen", "123456", 1.30005, "owner_food"
    )

    report = FoodEntityMatcher(source_ids=("owner_food",)).run(apply=True)

    assert report["outcomes"] == {"ambiguous": 1}
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM discovery_entity_relationships "
        "WHERE relationship_type = 'same_as'"
    )
    assert cursor.fetchone()[0] == 0
    conn.close()
