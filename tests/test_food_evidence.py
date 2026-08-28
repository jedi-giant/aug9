from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aug9.core import database
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
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "food-evidence.db")
    database.initialise_database()
    repository = DiscoveryRepository()
    repository.register_source(
        DiscoverySource(
            id="editorial",
            name="Authorised editorial source",
            permission=SourcePermission.LEGAL_REVIEWED,
        )
    )
    repository.upsert_entity(
        DiscoveryEntity(
            id="food:stall",
            entity_type=EntityType.FOOD_STALL,
            name="Example Chicken Rice",
        ),
        SourceRecord(
            source_id="editorial",
            external_id="venue-1",
            entity_id="food:stall",
        ),
        [],
    )
    return repository


def evidence(**updates) -> FoodEvidence:
    values = {
        "id": "evidence:article-1:chicken-rice",
        "entity_id": "food:stall",
        "external_id": "article-1:chicken-rice",
        "dimension": FoodEvidenceDimension.FOOD_QUALITY,
        "evidence_type": FoodEvidenceType.EDITORIAL,
        "direction": EvidenceDirection.POSITIVE,
        "claim_key": "dish_speciality",
        "value": {"dish": "chicken rice", "strength": "recommended"},
        "dish_name": "Chicken rice",
        "confidence": 0.8,
        "source_id": "editorial",
        "source_url": "https://food.example/article-1",
        "observed_at": datetime(2026, 8, 1, tzinfo=UTC),
        "expires_at": datetime(2027, 8, 1, tzinfo=UTC),
    }
    values.update(updates)
    return FoodEvidence(**values)


def test_food_evidence_is_idempotent_and_preserves_dimensions(repository):
    repository.upsert_food_evidence(evidence())
    repository.upsert_food_evidence(
        evidence(
            id="replacement-id-is-not-a-duplicate",
            confidence=0.9,
            commercial_status=CommercialStatus.SPONSORED,
        )
    )

    stored = repository.list_food_evidence(
        "food:stall", as_of=datetime(2026, 8, 28, tzinfo=UTC)
    )

    assert len(stored) == 1
    assert stored[0].dimension is FoodEvidenceDimension.FOOD_QUALITY
    assert stored[0].evidence_type is FoodEvidenceType.EDITORIAL
    assert stored[0].direction is EvidenceDirection.POSITIVE
    assert stored[0].value["dish"] == "chicken rice"
    assert stored[0].confidence == 0.9
    assert stored[0].commercial_status is CommercialStatus.SPONSORED


def test_expired_food_evidence_is_excluded_by_default(repository):
    repository.upsert_food_evidence(
        evidence(expires_at=datetime(2026, 8, 15, tzinfo=UTC))
    )

    active = repository.list_food_evidence(
        "food:stall", as_of=datetime(2026, 8, 28, tzinfo=UTC)
    )
    audit = repository.list_food_evidence(
        "food:stall",
        as_of=datetime(2026, 8, 28, tzinfo=UTC),
        include_expired=True,
    )

    assert active == []
    assert len(audit) == 1


def test_food_evidence_requires_ingestable_source(repository):
    repository.register_source(
        DiscoverySource(
            id="link_only_blog",
            name="Link-only blog",
            permission=SourcePermission.LINK_ONLY,
        )
    )

    with pytest.raises(ValueError, match="does not allow ingestion"):
        repository.upsert_food_evidence(evidence(source_id="link_only_blog"))


def test_food_evidence_rejects_inactive_source(repository):
    repository.register_source(
        DiscoverySource(
            id="retired_editorial",
            name="Retired editorial source",
            permission=SourcePermission.LEGAL_REVIEWED,
            active=False,
        )
    )

    with pytest.raises(ValueError, match="inactive"):
        repository.upsert_food_evidence(evidence(source_id="retired_editorial"))


def test_food_evidence_validates_confidence_and_freshness():
    with pytest.raises(ValidationError, match="less than or equal to 1"):
        evidence(confidence=1.1)
    with pytest.raises(ValidationError, match="expires_at"):
        evidence(expires_at=datetime(2026, 7, 31, tzinfo=UTC))


def test_food_evidence_requires_existing_entity(repository):
    with pytest.raises(ValueError, match="does not exist"):
        repository.upsert_food_evidence(evidence(entity_id="food:missing"))


def test_food_evidence_query_is_bounded(repository):
    with pytest.raises(ValueError, match="between 1 and 500"):
        repository.list_food_evidence("food:stall", limit=501)
