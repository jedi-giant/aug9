from datetime import UTC, datetime

import pytest

from aug9.core import database
from aug9.discovery.food_ranking_shadow import build_food_ranking_shadow_report
from aug9.discovery.food_ranking_shadow import (
    _candidate_category,
    _relevance_score,
    _request_category,
)
from aug9.discovery.models import (
    CommercialStatus,
    DiscoverySource,
    EvidenceDirection,
    FoodEvidence,
    FoodEvidenceDimension,
    FoodEvidenceType,
    SourcePermission,
    DiscoveryEntity,
    EntityType,
    FieldProvenance,
    RelationshipType,
    SourceRecord,
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
    assert report["request"]["category"] == "meal"

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


def test_shadow_report_uses_editorial_evidence_from_verified_same_as_entity(
    repository,
):
    external = DiscoveryEntity(
        id="food:editorial:linked",
        entity_type=EntityType.FOOD_VENUE,
        name="Linked Editorial Venue",
        latitude=1.304,
        longitude=103.8,
    )
    repository.upsert_entity(
        external,
        SourceRecord(
            source_id="editorial",
            external_id="linked",
            entity_id=external.id,
        ),
        [
            FieldProvenance(
                entity_id=external.id,
                field_name="name",
                source_id="editorial",
                value=external.name,
            )
        ],
    )
    repository.upsert_food_evidence(
        FoodEvidence(
            id="editorial:linked",
            entity_id=external.id,
            external_id="linked",
            dimension=FoodEvidenceDimension.FOOD_QUALITY,
            evidence_type=FoodEvidenceType.EDITORIAL,
            direction=EvidenceDirection.POSITIVE,
            claim_key="editorial_recommendation",
            value={"recommended": True},
            confidence=0.8,
            source_id="editorial",
            observed_at=datetime(2026, 8, 1, tzinfo=UTC),
            expires_at=datetime(2027, 8, 1, tzinfo=UTC),
            commercial_status=CommercialStatus.ORGANIC,
        )
    )
    repository.add_relationship(
        "food:nearest",
        external.id,
        RelationshipType.SAME_AS,
        source_id="editorial",
    )

    report = build_food_ranking_shadow_report(
        DatabaseFoodProvider(limit=10, max_distance_km=3),
        latitude=1.3,
        longitude=103.8,
        now=datetime(2026, 8, 29, tzinfo=UTC),
    )

    nearest = next(
        item for item in report["candidates"] if item["entity_id"] == "food:nearest"
    )
    assert nearest["positive_organic_editorial_records"] == 1


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


def test_intent_categories_are_conservative_and_query_aware():
    assert _candidate_category("1950 COFFEE") == "beverage"
    assert _candidate_category("Fresh Fruit Juice") == "beverage"
    assert _candidate_category("Ah Tai Hainanese Chicken Rice") == "meal"
    assert _candidate_category("Han Kee") == "unknown"
    assert _request_category("Find coffee near me") == "beverage"
    assert _request_category("Where should I have lunch?") == "meal"
    assert _relevance_score("beverage", "meal") == 0.3
    assert _relevance_score("unknown", "meal") == 0.7


def test_meal_shortlist_does_not_use_beverage_as_closest(repository):
    conn = database.get_connection()
    cursor = conn.cursor()
    observed = datetime(2026, 8, 1, tzinfo=UTC).isoformat()
    for entity_id, name, latitude in (
        ("food:coffee", "1950 Coffee", 1.30001),
        ("food:rice", "Chicken Rice", 1.30002),
    ):
        cursor.execute(
            "INSERT INTO discovery_entities "
            "(id, entity_type, name, address, postal_code, latitude, longitude, status) "
            "VALUES (?, 'food_stall', ?, 'Same Centre', '123456', ?, 103.8, 'active')",
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

    report = build_food_ranking_shadow_report(
        DatabaseFoodProvider(limit=10, max_distance_km=3),
        latitude=1.3,
        longitude=103.8,
        now=datetime(2026, 8, 29, tzinfo=UTC),
        pool_limit=10,
        display_limit=5,
        request_text="Find lunch near me",
    )

    closest = next(
        item
        for item in report["recommended_shortlist"]
        if item["role"] == "closest_suitable"
    )
    assert closest["name"] == "Chicken Rice"
    assert closest["candidate_category"] == "meal"
