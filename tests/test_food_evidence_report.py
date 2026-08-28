from datetime import UTC, datetime

import pytest

from aug9.core import database
from aug9.discovery.food_evidence_report import build_food_evidence_report
from aug9.discovery.models import (
    CommercialStatus,
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    EvidenceDirection,
    FoodEvidence,
    FoodEvidenceDimension,
    FoodEvidenceType,
    SourcePermission,
    SourceRecord,
)
from aug9.discovery.repository import DiscoveryRepository


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "evidence-report.db")
    database.initialise_database()
    repository = DiscoveryRepository()
    source = DiscoverySource(
        id="editorial",
        name="Editorial",
        permission=SourcePermission.LEGAL_REVIEWED,
    )
    repository.register_source(source)
    repository.upsert_entity(
        DiscoveryEntity(
            id="food:1",
            entity_type=EntityType.FOOD_STALL,
            name="Food One",
        ),
        SourceRecord(
            source_id=source.id,
            external_id="food-1",
            entity_id="food:1",
        ),
        [],
    )
    return repository


def test_food_evidence_report_separates_active_and_expired(repository):
    for external_id, expires_at, commercial_status in (
        (
            "active",
            datetime(2027, 1, 1, tzinfo=UTC),
            CommercialStatus.ORGANIC,
        ),
        (
            "expired",
            datetime(2026, 1, 1, tzinfo=UTC),
            CommercialStatus.SPONSORED,
        ),
    ):
        repository.upsert_food_evidence(
            FoodEvidence(
                id=f"evidence:{external_id}",
                entity_id="food:1",
                external_id=external_id,
                dimension=FoodEvidenceDimension.FOOD_QUALITY,
                evidence_type=FoodEvidenceType.EDITORIAL,
                direction=EvidenceDirection.POSITIVE,
                claim_key="dish_speciality",
                value={"dish": "chicken rice"},
                dish_name="Chicken rice",
                confidence=0.8,
                source_id="editorial",
                observed_at=datetime(2025, 1, 1, tzinfo=UTC),
                expires_at=expires_at,
                commercial_status=commercial_status,
            )
        )

    report = build_food_evidence_report(
        now=datetime(2026, 8, 28, tzinfo=UTC)
    )

    assert report.total_records == 2
    assert report.active_records == 1
    assert report.expired_records == 1
    assert report.covered_entities == 1
    assert report.dish_specific_records == 2
    assert report.records_by_dimension == {"food_quality": 2}
    assert report.records_by_type == {"editorial": 2}
    assert report.records_by_commercial_status == {
        "organic": 1,
        "sponsored": 1,
    }
