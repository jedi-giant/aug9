from datetime import UTC, datetime

import pytest

from aug9.core import database
from aug9.discovery.food_ranking_shadow import build_food_ranking_shadow_report
from aug9.discovery.models import (
    CommercialStatus,
    DiscoverySource,
    EvidenceDirection,
    FoodEvidence,
    FoodEvidenceDimension,
    FoodEvidenceType,
    SourcePermission,
)
from aug9.discovery.repository import DiscoveryRepository
from aug9.discovery.sfa_food_establishments import SFA_SOURCE_ID
from aug9.sg_food.provider import DatabaseFoodProvider


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "ranking-shadow.db")
    database.initialise_database()
    repository = DiscoveryRepository()
    for source in (
        DiscoverySource(
            id=SFA_SOURCE_ID,
            name="SFA",
            permission=SourcePermission.OPEN_DATA,
        ),
        DiscoverySource(
            id="editorial",
            name="Editorial",
            permission=SourcePermission.LEGAL_REVIEWED,
        ),
    ):
        repository.register_source(source)
    conn = database.get_connection()
    cursor = conn.cursor()
    observed = datetime(2026, 8, 1, tzinfo=UTC).isoformat()
    for entity_id, name, latitude in (
        ("food:nearest", "Nearest Stall", 1.3001),
        ("food:editorial", "Editorial Stall", 1.304),
    ):
        cursor.execute(
            "INSERT INTO discovery_entities "
            "(id, entity_type, name, address, postal_code, latitude, longitude, status) "
            "VALUES (?, 'food_stall', ?, 'Example Street', '123456', ?, 103.8, 'active')",
            (entity_id, name, latitude),
        )
        cursor.execute(
            "INSERT INTO discovery_source_records "
            "(source_id, external_id, entity_id, raw_payload, fetched_at) "
            "VALUES (?, ?, ?, '{}', ?)",
            (SFA_SOURCE_ID, entity_id, entity_id, observed),
        )
        cursor.execute(
            "INSERT INTO discovery_food_profiles "
            "(entity_id, venue_kind, currency, dietary_attributes, source_id) "
            "VALUES (?, 'hawker_stall', 'SGD', '[]', ?)",
            (entity_id, SFA_SOURCE_ID),
        )
        cursor.execute(
            "INSERT INTO discovery_food_safety_profiles "
            "(entity_id, licence_number, safe_grade, business_type, source_id, observed_at) "
            "VALUES (?, ?, 'A', 'Food Stall', ?, ?)",
            (entity_id, entity_id, SFA_SOURCE_ID, observed),
        )
    conn.commit()
    conn.close()
    repository.upsert_food_evidence(
        FoodEvidence(
            id="editorial:one",
            entity_id="food:editorial",
            external_id="one",
            dimension=FoodEvidenceDimension.FOOD_QUALITY,
            evidence_type=FoodEvidenceType.EDITORIAL,
            direction=EvidenceDirection.POSITIVE,
            claim_key="award_or_recognition",
            value={"award": "Example"},
            confidence=0.8,
            source_id="editorial",
            observed_at=datetime(2026, 8, 1, tzinfo=UTC),
            expires_at=datetime(2027, 8, 1, tzinfo=UTC),
            commercial_status=CommercialStatus.ORGANIC,
        )
    )
    return repository


def test_shadow_report_compares_real_candidate_orders_without_mutation(repository):
    report = build_food_ranking_shadow_report(
        DatabaseFoodProvider(limit=10, max_distance_km=3),
        latitude=1.3,
        longitude=103.8,
        now=datetime(2026, 8, 29, tzinfo=UTC),
    )

    assert report["mode"] == "shadow"
    assert report["live_ranking_affected"] is False
    assert report["pool_candidate_count"] == 2
    assert report["displayed_candidate_count"] == 2
    assert report["editorial_candidate_count"] == 1
    assert report["distance_ties"]["largest_same_coordinate_group"] == 1
    assert report["candidates"][0]["entity_id"] == "food:editorial"
    assert report["candidates"][0]["current_distance_rank"] == 2
    assert report["candidates"][0]["proposed_rank"] == 1
    assert report["candidates"][0]["positive_organic_editorial_records"] == 1
    assert [item["role"] for item in report["recommended_shortlist"]] == [
        "best_supported",
        "closest_suitable",
    ]
    assert report["shortlist_count"] == 2

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM discovery_food_evidence")
    assert cursor.fetchone()[0] == 1
    conn.close()


def test_shadow_report_handles_no_nearby_candidates(repository):
    report = build_food_ranking_shadow_report(
        DatabaseFoodProvider(limit=10, max_distance_km=0.1),
        latitude=1.4,
        longitude=103.9,
    )

    assert report["pool_candidate_count"] == 0
    assert report["displayed_candidate_count"] == 0
    assert report["rank_changes"] == 0
    assert report["recommended_shortlist"] == []


def test_shadow_report_scores_a_larger_pool_before_display_limit(repository):
    report = build_food_ranking_shadow_report(
        DatabaseFoodProvider(limit=1, max_distance_km=3),
        latitude=1.3,
        longitude=103.8,
        now=datetime(2026, 8, 29, tzinfo=UTC),
        pool_limit=2,
        display_limit=1,
    )

    assert report["pool_candidate_count"] == 2
    assert report["displayed_candidate_count"] == 1
    assert report["candidates"][0]["entity_id"] == "food:editorial"


def test_shortlist_uses_distinct_location_for_third_choice(repository):
    conn = database.get_connection()
    cursor = conn.cursor()
    observed = datetime(2026, 8, 1, tzinfo=UTC).isoformat()
    cursor.execute(
        "INSERT INTO discovery_entities "
        "(id, entity_type, name, address, postal_code, latitude, longitude, status) "
        "VALUES ('food:alternative', 'food_stall', 'Alternative Stall', "
        "'Other Street', '654321', 1.306, 103.802, 'active')"
    )
    cursor.execute(
        "INSERT INTO discovery_source_records "
        "(source_id, external_id, entity_id, raw_payload, fetched_at) "
        "VALUES (?, 'food:alternative', 'food:alternative', '{}', ?)",
        (SFA_SOURCE_ID, observed),
    )
    cursor.execute(
        "INSERT INTO discovery_food_profiles "
        "(entity_id, venue_kind, currency, dietary_attributes, source_id) "
        "VALUES ('food:alternative', 'hawker_stall', 'SGD', '[]', ?)",
        (SFA_SOURCE_ID,),
    )
    cursor.execute(
        "INSERT INTO discovery_food_safety_profiles "
        "(entity_id, licence_number, safe_grade, business_type, source_id, observed_at) "
        "VALUES ('food:alternative', 'food:alternative', 'A', 'Food Stall', ?, ?)",
        (SFA_SOURCE_ID, observed),
    )
    conn.commit()
    conn.close()

    report = build_food_ranking_shadow_report(
        DatabaseFoodProvider(limit=10, max_distance_km=3),
        latitude=1.3,
        longitude=103.8,
        now=datetime(2026, 8, 29, tzinfo=UTC),
        pool_limit=10,
        display_limit=3,
    )

    assert [item["role"] for item in report["recommended_shortlist"]] == [
        "best_supported",
        "closest_suitable",
        "nearby_alternative",
    ]
    assert report["recommended_shortlist"][2]["name"] == "Alternative Stall"
