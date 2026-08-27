import csv
import json

import pytest

from aug9.core import database
from aug9.discovery.food_profiles import FoodProfileImporter
from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    SourcePermission,
    SourceRecord,
)
from aug9.discovery.repository import DiscoveryRepository


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "food-profiles.db")
    database.initialise_database()
    return DiscoveryRepository()


def authorised_source():
    return DiscoverySource(
        id="authorised_food",
        name="Authorised Food Partner",
        permission=SourcePermission.LICENSED_PARTNER,
        attribution="Authorised Food Partner",
        license_name="Partner agreement",
    )


def test_controlled_food_profile_import(repository, tmp_path):
    source = authorised_source()
    repository.register_source(source)
    parent = DiscoveryEntity(
        id="hawker:maxwell",
        entity_type=EntityType.HAWKER_CENTRE,
        name="Maxwell Food Centre",
        latitude=1.2803,
        longitude=103.8447,
    )
    repository.upsert_entity(
        parent,
        SourceRecord(
            source_id=source.id,
            external_id="maxwell",
            entity_id=parent.id,
        ),
        [],
    )
    path = tmp_path / "food.csv"
    fields = [
        "external_id", "name", "parent_entity_id", "price_min", "price_max",
        "dietary_attributes", "cuisine", "dish", "opening_hours_json",
        "source_url",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "external_id": "stall-1",
                "name": "Verified Halal Lunch",
                "parent_entity_id": parent.id,
                "price_min": "6",
                "price_max": "12",
                "dietary_attributes": "halal",
                "cuisine": "Malay|Singaporean",
                "dish": "nasi padang",
                "opening_hours_json": json.dumps(
                    [
                        {
                            "day_of_week": 0,
                            "opens_at": "08:00",
                            "closes_at": "20:00",
                        }
                    ]
                ),
                "source_url": "https://partner.example/stall-1",
            }
        )

    summary = FoodProfileImporter(repository, source).run(path)
    listings = repository.search_food_listings()

    assert summary.received == 1
    assert summary.upserted == 1
    assert summary.rejected == 0
    assert listings[0].profile.price_max == 12
    assert listings[0].profile.dietary_attributes == ["halal"]
    assert listings[0].tags["cuisine"] == ["Malay", "Singaporean"]
    assert listings[0].parent.id == parent.id
    assert listings[0].opening_periods[0].closes_at == "20:00"


def test_food_profile_import_rejects_unknown_parent(repository, tmp_path):
    path = tmp_path / "food.csv"
    path.write_text(
        "external_id,name,parent_entity_id\n"
        "stall-1,Unlinked Stall,hawker:missing\n",
        encoding="utf-8",
    )

    summary = FoodProfileImporter(repository, authorised_source()).run(path)

    assert summary.received == 1
    assert summary.upserted == 0
    assert summary.rejected == 1
    assert repository.search_food_listings() == []


def test_food_profile_import_requires_ingestable_attributed_source(repository):
    with pytest.raises(ValueError, match="does not allow ingestion"):
        FoodProfileImporter(
            repository,
            DiscoverySource(
                id="research",
                name="Research only",
                permission=SourcePermission.RESEARCH_ONLY,
                attribution="Research source",
            ),
        )

    with pytest.raises(ValueError, match="attribution is required"):
        FoodProfileImporter(
            repository,
            DiscoverySource(
                id="missing_attribution",
                name="Missing attribution",
                permission=SourcePermission.LEGAL_REVIEWED,
            ),
        )
