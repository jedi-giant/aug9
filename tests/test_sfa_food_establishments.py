import json

import httpx
import pytest

from aug9.core import database
from aug9.discovery.repository import DiscoveryRepository
from aug9.discovery.sfa_food_establishments import (
    SFA_SOURCE_ID,
    SfaFoodEstablishmentImporter,
)


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "sfa-food.db")
    database.initialise_database()
    return DiscoveryRepository()


def test_sfa_importer_adds_named_restaurants_and_stalls_without_licensee_names(
    repository,
):
    records = {
        "Restaurant": [
            {
                "refNo": "R1",
                "applType": "EHFE",
                "establishmentAddress": "1 TEST STREET Singapore 123456",
                "licenceNumber": "R1",
                "businessName": "Test Restaurant",
                "licenseeName": "PRIVATE PERSON",
                "typeOfFoodBussiness": "Restaurant",
                "grades": "A",
            }
        ],
        "NEA Managed Foodstall": [
            {
                "refNo": "S1",
                "applType": "EHFE",
                "establishmentAddress": "335 SMITH STREET #02-01 Singapore 050335",
                "licenceNumber": "S1",
                "businessName": "Test Noodles",
                "licenseeName": "ANOTHER PRIVATE PERSON",
                "typeOfFoodBussiness": "NEA Managed Foodstall",
                "grades": "New",
            },
            {
                "refNo": "S2",
                "applType": "EHFE",
                "establishmentAddress": "335 SMITH STREET #02-02 Singapore 050335",
                "licenceNumber": "S2",
                "businessName": "NA",
                "licenseeName": "PERSONAL NAME MUST NOT BE USED",
                "typeOfFoodBussiness": "NEA Managed Foodstall",
                "grades": "B",
            },
        ],
    }
    requested_types = []

    def handler(request: httpx.Request) -> httpx.Response:
        business_type = request.url.params["typeOfFoodBussiness"]
        requested_types.append(business_type)
        return httpx.Response(200, json={"data": records[business_type]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    importer = SfaFoodEstablishmentImporter(
        repository,
        client,
        business_types=("Restaurant", "NEA Managed Foodstall"),
        request_delay_seconds=0,
    )

    summary = importer.run()

    assert requested_types == ["Restaurant", "NEA Managed Foodstall"]
    assert summary.received == 3
    assert summary.upserted == 2
    assert summary.rejected == 1

    listings = repository.search_food_listings()
    assert {item.entity.name for item in listings} == {
        "Test Restaurant",
        "Test Noodles",
    }
    assert {item.profile.venue_kind for item in listings} == {
        "restaurant",
        "hawker_stall",
    }

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT licence_number, safe_grade, business_type FROM discovery_food_safety_profiles ORDER BY licence_number"
    )
    assert cursor.fetchall() == [
        ("R1", "A", "Restaurant"),
        ("S1", "New", "NEA Managed Foodstall"),
    ]
    cursor.execute(
        "SELECT raw_payload FROM discovery_source_records WHERE source_id = ?",
        (SFA_SOURCE_ID,),
    )
    payloads = [json.loads(row[0]) for row in cursor.fetchall()]
    conn.close()
    assert all("licenseeName" not in payload for payload in payloads)


def test_sfa_normalisation_rejects_unknown_grade_and_personal_name_fallback():
    base = {
        "establishmentAddress": "1 TEST STREET Singapore 123456",
        "licenceNumber": "R1",
        "businessName": "Test Restaurant",
        "typeOfFoodBussiness": "Restaurant",
        "grades": "A",
    }

    with pytest.raises(ValueError, match="no consumer-facing"):
        SfaFoodEstablishmentImporter.normalise(
            {**base, "businessName": "NA", "licenseeName": "PERSON NAME"}
        )
    with pytest.raises(ValueError, match="unsupported SAFE grade"):
        SfaFoodEstablishmentImporter.normalise({**base, "grades": "D"})


def test_sfa_importer_rejects_unbounded_configuration(repository):
    with pytest.raises(ValueError, match="At least one"):
        SfaFoodEstablishmentImporter(repository, business_types=())
    with pytest.raises(ValueError, match="cannot be negative"):
        SfaFoodEstablishmentImporter(repository, request_delay_seconds=-1)


def test_sfa_importer_archives_records_missing_from_a_later_snapshot(repository):
    responses = [
        [{
            "establishmentAddress": "1 TEST STREET Singapore 123456",
            "licenceNumber": "R1",
            "businessName": "Closing Restaurant",
            "typeOfFoodBussiness": "Restaurant",
            "grades": "A",
        }],
        [],
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": responses.pop(0)})

    importer = SfaFoodEstablishmentImporter(
        repository,
        httpx.Client(transport=httpx.MockTransport(handler)),
        business_types=("Restaurant",),
        request_delay_seconds=0,
    )
    first = importer.run()
    assert first.upserted == 1
    entity_id = repository.search_entities("Closing Restaurant")[0].id

    second = importer.run()
    assert second.upserted == 0
    assert repository.get_entity(entity_id).status == "archived"
