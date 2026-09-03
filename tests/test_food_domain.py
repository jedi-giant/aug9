import json

import pytest
from pydantic import ValidationError

from aug9.core import database
from aug9.discovery.food_domain import FoodDomainDocument, FoodDomainImporter
from aug9.discovery.repository import DiscoveryRepository


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "food-domain.db")
    database.initialise_database()
    return DiscoveryRepository()


def domain_payload():
    return {
        "schema_version": "aug9.food-domain.v1",
        "generated_at": "2026-08-29T12:00:00+08:00",
        "source": {
            "id": "owner_collection",
            "name": "Owner collection",
            "permission": "user_provided",
            "attribution": "Supplied by the database owner",
        },
        "places": [
            {
                "external_id": "restaurant-1",
                "entity_type": "food_venue",
                "name": "Independent Restaurant",
                "location": {
                    "address": "1 Example Street, Singapore 123456",
                    "postal_code": "123456",
                    "latitude": 1.3,
                    "longitude": 103.8,
                },
                "food_profile": {
                    "venue_kind": "restaurant",
                    "cuisines": ["Singaporean"],
                    "signature_dishes": ["Fish soup"],
                    "dietary_attributes": ["halal"],
                    "price": {"currency": "SGD", "minimum": 8, "maximum": 18},
                },
                "opening_hours": [
                    {"day_of_week": 0, "opens_at": "10:00", "closes_at": "20:00"}
                ],
                "evidence": [
                    {
                        "external_id": "dish-claim-1",
                        "dimension": "food_quality",
                        "evidence_type": "community",
                        "direction": "positive",
                        "claim_key": "dish_speciality",
                        "value": {"dish": "Fish soup"},
                        "dish_name": "Fish soup",
                        "confidence": 0.7,
                        "observed_at": "2026-08-29T12:00:00+08:00",
                    }
                ],
                "provenance": {
                    "observed_at": "2026-08-29T12:00:00+08:00",
                    "notes": "Owner supplied",
                },
            },
            {
                "external_id": "stall-1",
                "entity_type": "food_stall",
                "name": "Neighbourhood Noodles",
                "location": {
                    "address": "2 Example Road, Singapore 123457",
                    "postal_code": "123457",
                    "latitude": 1.301,
                    "longitude": 103.801,
                },
                "parent": {
                    "external_id": "centre-1",
                    "name": "Example Food Centre",
                    "entity_type": "hawker_centre",
                    "location": {
                        "address": "2 Example Road, Singapore 123457",
                        "postal_code": "123457"
                    }
                },
                "food_profile": {
                    "venue_kind": "hawker_stall",
                    "cuisines": ["Chinese"],
                    "signature_dishes": ["Noodles"],
                    "price": {"minimum": 4, "maximum": 8},
                },
                "provenance": {"observed_at": "2026-08-29T12:00:00+08:00"},
            },
        ],
    }


def test_food_domain_imports_restaurant_stall_parent_hours_tags_and_evidence(
    repository, tmp_path
):
    path = tmp_path / "food-domain.json"
    path.write_text(json.dumps(domain_payload()), encoding="utf-8")

    summary = FoodDomainImporter(repository).run(path)
    listings = repository.search_food_listings()

    assert summary.received == 2
    assert summary.upserted == 2
    assert summary.rejected == 0
    assert {item.entity.name for item in listings} == {
        "Independent Restaurant",
        "Neighbourhood Noodles",
    }
    restaurant = next(
        item for item in listings if item.entity.name == "Independent Restaurant"
    )
    stall = next(item for item in listings if item.entity.name == "Neighbourhood Noodles")
    assert restaurant.tags["dish"] == ["Fish soup"]
    assert restaurant.opening_periods[0].closes_at == "20:00"
    assert stall.parent.name == "Example Food Centre"
    assert len(repository.list_food_evidence(restaurant.entity.id)) == 1


def test_food_domain_rejects_duplicate_external_ids():
    payload = domain_payload()
    payload["places"].append(payload["places"][0])

    with pytest.raises(ValidationError, match="external_id values must be unique"):
        FoodDomainDocument.model_validate(payload)


def test_food_domain_requires_parent_for_stalls():
    payload = domain_payload()
    payload["places"][1]["parent"] = None

    with pytest.raises(ValidationError, match="require a parent"):
        FoodDomainDocument.model_validate(payload)


def test_food_domain_bulk_imports_simple_place_records(repository, tmp_path):
    payload = domain_payload()
    place = payload["places"][0]
    place["opening_hours"] = []
    place["evidence"] = []
    place["food_profile"]["cuisines"] = []
    place["food_profile"]["signature_dishes"] = []
    payload["places"] = [place]
    path = tmp_path / "simple-food-domain.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    summary = FoodDomainImporter(repository).run(path)
    listings = repository.search_food_listings()

    assert summary.upserted == 1
    assert listings[0].entity.name == "Independent Restaurant"
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM discovery_field_provenance WHERE entity_id = ?",
        (listings[0].entity.id,),
    )
    assert cursor.fetchone()[0] >= 4
    conn.close()


def test_food_domain_can_deactivate_records_missing_from_new_snapshot(
    repository, tmp_path
):
    initial = domain_payload()
    path = tmp_path / "food-domain.json"
    path.write_text(json.dumps(initial), encoding="utf-8")
    FoodDomainImporter(repository).run(path)

    replacement = domain_payload()
    replacement["places"] = replacement["places"][:1]
    path.write_text(json.dumps(replacement), encoding="utf-8")
    FoodDomainImporter(repository).run(path, deactivate_missing=True)

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT status FROM discovery_entities
           WHERE id = 'food:owner_collection:stall-1'"""
    )
    assert cursor.fetchone()[0] == "inactive"
    conn.close()
