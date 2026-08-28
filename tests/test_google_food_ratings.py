from datetime import UTC, datetime

import pytest

from aug9.core import database
from aug9.discovery.google_food_ratings import (
    FoodPlaceCandidate,
    GoogleFoodPlaceLinker,
    PlaceSearchResult,
    RatingSnapshot,
    build_google_rating_gate_report,
    select_high_confidence_match,
)
from aug9.discovery.models import (
    CommercialStatus,
    DiscoverySource,
    EvidenceDirection,
    FoodEvidence,
    FoodEvidenceDimension,
    FoodEvidenceType,
    GooglePlaceLink,
    SourcePermission,
)
from aug9.discovery.repository import DiscoveryRepository
from aug9.discovery.sfa_food_establishments import SFA_SOURCE_ID


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "google-food.db")
    database.initialise_database()
    repository = DiscoveryRepository()
    repository.register_source(
        DiscoverySource(
            id=SFA_SOURCE_ID,
            name="SFA food establishments",
            permission=SourcePermission.OPEN_DATA,
        )
    )
    repository.register_source(
        DiscoverySource(
            id="trusted_editorial",
            name="Trusted editorial",
            permission=SourcePermission.LEGAL_REVIEWED,
        )
    )
    conn = database.get_connection()
    cursor = conn.cursor()
    now = datetime.now(UTC).isoformat()
    for entity_id, name, postal_code in (
        ("food:low", "Low Rated Noodles", "123456"),
        ("food:conflict", "Recognised Rice", "123457"),
    ):
        cursor.execute(
            "INSERT INTO discovery_entities "
            "(id, entity_type, name, address, postal_code, latitude, longitude, status) "
            "VALUES (?, 'food_stall', ?, ?, ?, 1.3, 103.8, 'active')",
            (entity_id, name, f"1 Example Street Singapore {postal_code}", postal_code),
        )
        cursor.execute(
            "INSERT INTO discovery_source_records "
            "(source_id, external_id, entity_id, raw_payload, fetched_at) "
            "VALUES (?, ?, ?, '{}', ?)",
            (SFA_SOURCE_ID, entity_id, entity_id, now),
        )
    conn.commit()
    conn.close()
    return repository


def candidate() -> FoodPlaceCandidate:
    return FoodPlaceCandidate(
        entity_id="food:low",
        name="Low Rated Noodles",
        address="1 Example Street Singapore 123456",
        postal_code="123456",
        latitude=1.3,
        longitude=103.8,
    )


def test_match_requires_name_and_branch_location_agreement():
    accepted = PlaceSearchResult(
        "google:accepted",
        "Low Rated Noodles",
        "1 Example Street, Singapore 123456",
        1.3001,
        103.8001,
    )
    wrong_branch = PlaceSearchResult(
        "google:wrong",
        "Low Rated Noodles",
        "99 Far Street, Singapore 654321",
        1.4,
        103.9,
    )

    match = select_high_confidence_match(candidate(), [wrong_branch, accepted])

    assert match is not None
    assert match[0].place_id == "google:accepted"
    assert match[1] >= 0.85


def test_ambiguous_matches_are_rejected():
    result = PlaceSearchResult(
        "google:one",
        "Low Rated Noodles",
        "1 Example Street, Singapore 123456",
        1.3,
        103.8,
    )
    duplicate = PlaceSearchResult(
        "google:two",
        "Low Rated Noodles",
        "1 Example Street, Singapore 123456",
        1.3,
        103.8,
    )

    assert select_high_confidence_match(candidate(), [result, duplicate]) is None


def test_linker_stores_only_google_place_identity(repository):
    class Places:
        def search(self, item):
            return [
                PlaceSearchResult(
                    f"google:{item.entity_id}",
                    item.name,
                    item.address,
                    item.latitude,
                    item.longitude,
                )
            ]

    summary = GoogleFoodPlaceLinker(repository, Places()).run(limit=10)
    links = repository.list_google_place_links()

    assert summary.linked == 2
    assert {link.entity_id for link in links} == {"food:low", "food:conflict"}
    assert all(link.match_confidence >= 0.85 for link in links)

    second_run = GoogleFoodPlaceLinker(repository, Places()).run(limit=10)
    assert second_run.received == 0


def test_shadow_report_suppresses_low_rating_but_escalates_conflict(repository):
    for entity_id in ("food:low", "food:conflict"):
        repository.upsert_google_place_link(
            GooglePlaceLink(
                entity_id=entity_id,
                place_id=f"google:{entity_id}",
                match_confidence=0.99,
            )
        )
    repository.upsert_food_evidence(
        FoodEvidence(
            id="trusted:recognition",
            entity_id="food:conflict",
            external_id="recognition",
            dimension=FoodEvidenceDimension.FOOD_QUALITY,
            evidence_type=FoodEvidenceType.EDITORIAL,
            direction=EvidenceDirection.POSITIVE,
            claim_key="award_or_recognition",
            value={"award": "Example"},
            confidence=0.8,
            source_id="trusted_editorial",
            observed_at=datetime(2026, 8, 1, tzinfo=UTC),
            expires_at=datetime(2027, 8, 1, tzinfo=UTC),
            commercial_status=CommercialStatus.ORGANIC,
        )
    )

    class Places:
        def rating(self, place_id):
            return RatingSnapshot(place_id, 2.4, 20, f"https://maps.google/{place_id}")

    report = build_google_rating_gate_report(repository, Places())

    assert report["mode"] == "shadow"
    assert report["decisions"] == {
        "shadow_suppress": 1,
        "conflicting_evidence_review": 1,
    }
    assert repository.get_entity("food:low").status == "active"


def test_shadow_report_does_not_penalise_small_review_samples(repository):
    repository.upsert_google_place_link(
        GooglePlaceLink(
            entity_id="food:low",
            place_id="google:low",
            match_confidence=0.99,
        )
    )

    class Places:
        def rating(self, place_id):
            return RatingSnapshot(place_id, 1.5, 3, None)

    report = build_google_rating_gate_report(repository, Places())

    assert report["decisions"] == {"insufficient_reviews": 1}
