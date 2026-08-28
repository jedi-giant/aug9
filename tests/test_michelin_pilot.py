from pathlib import Path

import pytest

from aug9.core import database
from aug9.discovery.michelin_pilot import (
    MichelinPilotCandidate,
    MichelinSfaMatcher,
    load_michelin_pilot,
)
from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    SourcePermission,
    SourceRecord,
)
from aug9.discovery.repository import DiscoveryRepository
from aug9.discovery.sfa_food_establishments import SFA_SOURCE_ID


PILOT_PATH = Path("data/michelin_singapore_bib_gourmand_pilot_2026.csv")


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "michelin.db")
    database.initialise_database()
    repository = DiscoveryRepository()
    repository.register_source(
        DiscoverySource(
            id=SFA_SOURCE_ID,
            name="SFA",
            permission=SourcePermission.OPEN_DATA,
        )
    )
    return repository


def add_food(repository, entity_id, name, latitude, longitude):
    repository.upsert_entity(
        DiscoveryEntity(
            id=entity_id,
            entity_type=EntityType.FOOD_VENUE,
            name=name,
            address="1 Example Street Singapore 123456",
            latitude=latitude,
            longitude=longitude,
        ),
        SourceRecord(
            source_id=SFA_SOURCE_ID,
            external_id=entity_id,
            entity_id=entity_id,
        ),
        [],
    )


def candidate(name="Kok Sen"):
    return MichelinPilotCandidate(
        external_id="501505",
        name=name,
        latitude=1.2802718,
        longitude=103.841681,
        distinction="BIB_GOURMAND",
        price_band="$$",
        cuisine="Singaporean",
        source_url="https://guide.michelin.com/example",
        observed_at="2026-08-28T12:00:00+08:00",
    )


def test_pilot_snapshot_contains_reviewable_structured_facts():
    rows = load_michelin_pilot(PILOT_PATH)

    assert len(rows) == 30
    assert all(item.distinction == "BIB_GOURMAND" for item in rows)
    assert all(item.source_url.startswith("https://guide.michelin.com/") for item in rows)


def test_matcher_marks_unambiguous_name_and_location_high_confidence(repository):
    add_food(repository, "food:kok-sen", "KOK SEN RESTAURANT", 1.28028, 103.84168)

    match = MichelinSfaMatcher().match(candidate())

    assert match.entity_id == "food:kok-sen"
    assert match.status == "high_confidence"
    assert match.name_similarity >= 0.9
    assert match.distance_km < 0.01

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM discovery_food_evidence")
    evidence_count = cursor.fetchone()[0]
    conn.close()
    assert evidence_count == 0


def test_matcher_requires_review_when_best_candidate_is_ambiguous(repository):
    add_food(repository, "food:one", "Kok Sen", 1.28028, 103.84168)
    add_food(repository, "food:two", "Kok Sen", 1.28029, 103.84169)

    match = MichelinSfaMatcher().match(candidate())

    assert match.status == "review"
    assert len(match.alternatives) == 2


def test_matcher_reports_unmatched_without_nearby_sfa_entity(repository):
    match = MichelinSfaMatcher().match(candidate())

    assert match.status == "unmatched"
    assert match.entity_id is None


def test_matcher_radius_is_bounded():
    with pytest.raises(ValueError, match="between 0 and 2"):
        MichelinSfaMatcher(radius_km=2.1)
