import csv
import json

import pytest

from aug9.core import database
from aug9.discovery.food_evidence_importer import (
    ALLOWED_COLUMNS,
    FoodEvidenceCsvImporter,
)
from aug9.discovery.models import (
    CommercialStatus,
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    FoodEvidenceDimension,
    SourcePermission,
    SourceRecord,
)
from aug9.discovery.repository import DiscoveryRepository


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "evidence-import.db")
    database.initialise_database()
    repository = DiscoveryRepository()
    catalog_source = DiscoverySource(
        id="sfa",
        name="SFA",
        permission=SourcePermission.OPEN_DATA,
    )
    repository.register_source(catalog_source)
    repository.upsert_entity(
        DiscoveryEntity(
            id="food:stall",
            entity_type=EntityType.FOOD_STALL,
            name="Example Stall",
        ),
        SourceRecord(
            source_id="sfa",
            external_id="licence-1",
            entity_id="food:stall",
        ),
        [],
    )
    return repository


def editorial_source(permission=SourcePermission.LEGAL_REVIEWED):
    return DiscoverySource(
        id="editorial",
        name="Authorised Editorial Source",
        permission=permission,
        attribution="Authorised Editorial Source",
    )


def valid_row(**updates):
    row = {
        "external_id": "article-1:dish-1",
        "entity_id": "food:stall",
        "dimension": "food_quality",
        "evidence_type": "editorial",
        "direction": "positive",
        "claim_key": "dish_speciality",
        "value_json": json.dumps({"dish": "chicken rice"}),
        "dish_name": "Chicken rice",
        "confidence": "0.8",
        "source_url": "https://food.example/article-1",
        "observed_at": "2026-08-01T00:00:00+08:00",
        "expires_at": "2027-08-01T00:00:00+08:00",
        "commercial_status": "organic",
    }
    row.update(updates)
    return row


def write_csv(path, rows, fieldnames=None):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames or sorted(ALLOWED_COLUMNS),
        )
        writer.writeheader()
        writer.writerows(rows)


def test_controlled_food_evidence_csv_import(repository, tmp_path):
    path = tmp_path / "evidence.csv"
    write_csv(path, [valid_row()])

    summary = FoodEvidenceCsvImporter(
        repository, editorial_source()
    ).run(path)
    stored = repository.list_food_evidence("food:stall")

    assert summary.received == 1
    assert summary.upserted == 1
    assert summary.rejected == 0
    assert stored[0].dimension is FoodEvidenceDimension.FOOD_QUALITY
    assert stored[0].value == {"dish": "chicken rice"}
    assert stored[0].commercial_status is CommercialStatus.ORGANIC


@pytest.mark.parametrize(
    "updates",
    [
        {"confidence": "0.9"},
        {"claim_key": "copyrighted_description"},
        {"value_json": json.dumps("unstructured prose")},
        {"source_url": "http://food.example/article-1"},
        {"observed_at": "2026-08-01T00:00:00"},
        {"evidence_type": "community"},
        {"claim_key": "queue", "dimension": "food_quality"},
    ],
)
def test_controlled_import_rejects_unsafe_or_unsupported_rows(
    repository, tmp_path, updates
):
    path = tmp_path / "invalid.csv"
    write_csv(path, [valid_row(**updates)])

    summary = FoodEvidenceCsvImporter(repository, editorial_source()).run(path)

    assert summary.received == 1
    assert summary.upserted == 0
    assert summary.rejected == 1


def test_controlled_import_rejects_unknown_columns(repository, tmp_path):
    path = tmp_path / "unknown-column.csv"
    row = valid_row(description="Long copied article text")
    write_csv(path, [row], fieldnames=[*sorted(ALLOWED_COLUMNS), "description"])

    with pytest.raises(ValueError, match="Unsupported columns"):
        FoodEvidenceCsvImporter(repository, editorial_source()).run(path)


def test_controlled_import_requires_reviewed_or_licensed_source(repository):
    with pytest.raises(ValueError, match="licensed or legally reviewed"):
        FoodEvidenceCsvImporter(
            repository,
            editorial_source(permission=SourcePermission.OPEN_DATA),
        )
