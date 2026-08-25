import json

import httpx
import pytest

from aug9.core import database
from aug9.discovery.hlb_hotels import DATASET_URL, HlbHotelImporter
from aug9.discovery.models import EntityType
from aug9.discovery.repository import DiscoveryRepository


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "hotels.db")
    database.initialise_database()
    return DiscoveryRepository()


def test_hlb_hotel_importer_batches_valid_records(repository):
    download_url = "https://blobs.data.gov.sg/hotels.geojson"
    valid = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [103.8501, 1.2991]},
        "properties": {
            "OBJECTID": 19844,
            "HYPERLINK": "enquiries@example.com",
            "DESCRIPTION": None,
            "POSTALCODE": "189626",
            "KEEPERNAME": "Personal Name",
            "TOTALROOMS": "1,084",
            "FMEL_UPD_D": "20220713235853",
            "NAME": "Hotel Bencoolen",
        },
    }
    invalid = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [0, 0]},
        "properties": {"OBJECTID": 1, "NAME": "Invalid"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == DATASET_URL:
            return httpx.Response(200, json={"data": {"url": download_url}})
        if str(request.url) == download_url:
            return httpx.Response(200, json={
                "type": "FeatureCollection", "features": [valid, invalid]
            })
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    summary = HlbHotelImporter(repository, client).run()

    matches = repository.search_entities(
        "Bencoolen", entity_type=EntityType.HOTEL.value
    )
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT room_count, source_updated_at FROM discovery_hotel_profiles"
    )
    profile = cursor.fetchone()
    cursor.execute("SELECT raw_payload FROM discovery_source_records")
    raw_payload = json.loads(cursor.fetchone()[0])
    cursor.execute(
        "SELECT field_name FROM discovery_field_provenance ORDER BY field_name"
    )
    fields = [row[0] for row in cursor.fetchall()]
    conn.close()

    assert summary.received == 2
    assert summary.upserted == 1
    assert summary.rejected == 1
    assert len(matches) == 1
    assert matches[0].postal_code == "189626"
    assert profile == (1084, "20220713235853")
    assert "KEEPERNAME" not in raw_payload["properties"]
    assert "HYPERLINK" not in raw_payload["properties"]
    assert "keeper_name" not in fields
    assert "hyperlink" not in fields


def test_hlb_hotel_importer_is_idempotent(repository):
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [103.85, 1.3]},
        "properties": {
            "OBJECTID": 99,
            "POSTALCODE": "018956",
            "TOTALROOMS": "100",
            "NAME": "Example Hotel",
        },
    }
    importer = HlbHotelImporter(repository)
    repository.register_source(importer_source())
    hotel = importer.normalise(feature)

    importer.upsert_batch([hotel])
    updated_feature = {
        **feature,
        "properties": {**feature["properties"], "TOTALROOMS": "120"},
    }
    importer.upsert_batch([importer.normalise(updated_feature)])

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM discovery_entities")
    entity_count = cursor.fetchone()[0]
    cursor.execute("SELECT room_count FROM discovery_hotel_profiles")
    room_count = cursor.fetchone()[0]
    conn.close()

    assert entity_count == 1
    assert room_count == 120


def importer_source():
    from aug9.discovery.hlb_hotels import HLB_HOTELS_SOURCE_ID
    from aug9.discovery.models import DiscoverySource, SourcePermission

    return DiscoverySource(
        id=HLB_HOTELS_SOURCE_ID,
        name="Licensed Hotels",
        permission=SourcePermission.OPEN_DATA,
    )
