import json

import httpx
import pytest

from aug9.core import database
from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    FieldProvenance,
    FoodProfile,
    OpeningPeriod,
    RelationshipType,
    SourcePermission,
    SourceRecord,
)
from aug9.discovery.repository import DiscoveryRepository
from aug9.discovery.nea_hawkers import DATASET_URL, NeaHawkerImporter


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "discovery.db")
    database.initialise_database()
    return DiscoveryRepository()


def register_nea(repository: DiscoveryRepository) -> None:
    repository.register_source(
        DiscoverySource(
            id="nea_hawkers",
            name="NEA Hawker Centres",
            permission=SourcePermission.OPEN_DATA,
            base_url="https://data.gov.sg",
            license_name="Singapore Open Data Licence",
            attribution="National Environment Agency",
        )
    )


def test_open_source_record_is_upserted_with_provenance(repository):
    register_nea(repository)
    entity = DiscoveryEntity(
        id="hawker:maxwell",
        entity_type=EntityType.HAWKER_CENTRE,
        name="Maxwell Food Centre",
        address="1 Kadayanallur Street",
        postal_code="069184",
        quality_score=0.9,
    )
    record = SourceRecord(
        source_id="nea_hawkers",
        external_id="nea-123",
        entity_id=entity.id,
        raw_payload={"NAME": "Maxwell Food Centre"},
    )
    provenance = [
        FieldProvenance(
            entity_id=entity.id,
            field_name="name",
            source_id=record.source_id,
            value=entity.name,
        )
    ]

    first_id = repository.upsert_entity(entity, record, provenance)
    updated = entity.model_copy(update={"quality_score": 1.0})
    second_id = repository.upsert_entity(updated, record, provenance)

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT quality_score FROM discovery_entities WHERE id = ?",
        (entity.id,),
    )
    quality_score = cursor.fetchone()[0]
    cursor.execute("SELECT raw_payload FROM discovery_source_records")
    raw_payload = json.loads(cursor.fetchone()[0])
    cursor.execute("SELECT COUNT(*) FROM discovery_field_provenance")
    provenance_count = cursor.fetchone()[0]
    conn.close()

    assert first_id == second_id
    assert quality_score == 1.0
    assert raw_payload == {"NAME": "Maxwell Food Centre"}
    assert provenance_count == 1

    stored = repository.get_entity(entity.id)
    matches = repository.search_entities(
        "maxwell",
        entity_type=EntityType.HAWKER_CENTRE.value,
    )

    assert stored is not None
    assert stored.name == "Maxwell Food Centre"
    assert [match.id for match in matches] == [entity.id]


@pytest.mark.parametrize(
    "permission",
    [
        SourcePermission.LINK_ONLY,
        SourcePermission.RESEARCH_ONLY,
        SourcePermission.PROHIBITED,
    ],
)
def test_non_ingestable_source_is_blocked(repository, permission):
    repository.register_source(
        DiscoverySource(
            id="editorial_source",
            name="Editorial source",
            permission=permission,
        )
    )
    entity = DiscoveryEntity(
        id="food:example",
        entity_type=EntityType.FOOD_VENUE,
        name="Example Restaurant",
    )
    record = SourceRecord(
        source_id="editorial_source",
        external_id="article-1",
        entity_id=entity.id,
    )

    with pytest.raises(ValueError, match="does not allow ingestion"):
        repository.upsert_entity(entity, record, [])


def test_ingestion_run_records_counts(repository):
    register_nea(repository)

    run = repository.start_ingestion("nea_hawkers")
    completed = repository.complete_ingestion(
        run,
        records_received=120,
        records_upserted=118,
        records_rejected=2,
    )

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT status, records_received, records_upserted, records_rejected
        FROM discovery_ingestion_runs WHERE id = ?
        """,
        (run.id,),
    )
    row = cursor.fetchone()
    conn.close()

    assert completed.status == "completed"
    assert completed.completed_at is not None
    assert row == ("completed", 120, 118, 2)


def test_nea_hawker_importer_upserts_valid_features(repository):
    download_url = "https://blobs.data.gov.sg/hawkers.geojson"
    valid_feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [103.844747, 1.280331]},
        "properties": {
            "OBJECTID": 123,
            "NAME": "Maxwell Food Centre",
            "ADDRESS_MYENV": "1 Kadayanallur Street, Singapore 069184",
            "ADDRESSPOSTALCODE": "069184",
            "STATUS": "Existing",
        },
    }
    invalid_feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [0, 0]},
        "properties": {"OBJECTID": 999, "NAME": "Invalid"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == DATASET_URL:
            return httpx.Response(200, json={"data": {"url": download_url}})
        if str(request.url) == download_url:
            return httpx.Response(
                200,
                json={
                    "type": "FeatureCollection",
                    "features": [valid_feature, invalid_feature],
                },
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    summary = NeaHawkerImporter(repository, client).run()
    matches = repository.search_entities("Maxwell")

    assert summary.received == 2
    assert summary.upserted == 1
    assert summary.rejected == 1
    assert matches[0].postal_code == "069184"
    assert matches[0].status == "active"


def test_food_profile_relationship_tags_and_hours(repository):
    register_nea(repository)
    parent = DiscoveryEntity(
        id="hawker:maxwell",
        entity_type=EntityType.HAWKER_CENTRE,
        name="Maxwell Food Centre",
    )
    stall = DiscoveryEntity(
        id="stall:tian-tian",
        entity_type=EntityType.FOOD_STALL,
        name="Tian Tian Hainanese Chicken Rice",
    )
    for entity in (parent, stall):
        repository.upsert_entity(
            entity,
            SourceRecord(
                source_id="nea_hawkers",
                external_id=entity.id,
                entity_id=entity.id,
            ),
            [],
        )

    repository.add_relationship(
        parent.id,
        stall.id,
        RelationshipType.CONTAINS,
        source_id="nea_hawkers",
    )
    repository.upsert_food_profile(
        FoodProfile(
            entity_id=stall.id,
            venue_kind="hawker_stall",
            price_min=4,
            price_max=8,
            dietary_attributes=["contains_meat"],
        ),
        source_id="nea_hawkers",
        tags={"cuisine": ["Singaporean"], "dish": ["chicken rice"]},
    )
    repository.replace_opening_hours(
        stall.id,
        [
            OpeningPeriod(
                entity_id=stall.id,
                day_of_week=1,
                opens_at="10:00",
                closes_at="19:30",
                source_id="nea_hawkers",
            )
        ],
        source_id="nea_hawkers",
    )

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM discovery_entity_relationships")
    relationship_count = cursor.fetchone()[0]
    cursor.execute(
        "SELECT venue_kind, price_min, price_max FROM discovery_food_profiles"
    )
    profile = cursor.fetchone()
    cursor.execute("SELECT category, tag FROM discovery_entity_tags ORDER BY category")
    tags = cursor.fetchall()
    cursor.execute(
        "SELECT day_of_week, opens_at, closes_at FROM discovery_opening_hours"
    )
    hours = cursor.fetchone()
    conn.close()

    assert relationship_count == 1
    assert profile == ("hawker_stall", 4.0, 8.0)
    assert tags == [("cuisine", "Singaporean"), ("dish", "chicken rice")]
    assert hours == (1, "10:00", "19:30")
