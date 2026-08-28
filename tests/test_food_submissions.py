import pytest

from aug9.api.admin_auth import (
    AdminAuthenticationConfigurationError,
    AdminAuthenticationError,
    verify_admin_api_key,
)
from aug9.core import database
from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    SourcePermission,
    SourceRecord,
)
from aug9.discovery.repository import DiscoveryRepository
from aug9.discovery.submissions import (
    FoodSubmissionCreate,
    FoodSubmissionRepository,
    SubmissionStatus,
    SubmissionType,
)


@pytest.fixture
def submission_repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "submissions.db")
    database.initialise_database()
    discovery = DiscoveryRepository()
    discovery.register_source(
        DiscoverySource(
            id="nea_hawkers",
            name="NEA Hawker Centres",
            permission=SourcePermission.OPEN_DATA,
        )
    )
    centre = DiscoveryEntity(
        id="hawker:maxwell",
        entity_type=EntityType.HAWKER_CENTRE,
        name="Maxwell Food Centre",
    )
    discovery.upsert_entity(
        centre,
        SourceRecord(
            source_id="nea_hawkers",
            external_id="maxwell",
            entity_id=centre.id,
        ),
        [],
    )
    return FoodSubmissionRepository(), discovery


def test_admin_api_key_is_required_and_compared(monkeypatch):
    monkeypatch.delenv("AUG9_ADMIN_API_KEY", raising=False)
    with pytest.raises(AdminAuthenticationConfigurationError):
        verify_admin_api_key("x" * 32)

    monkeypatch.setenv("AUG9_ADMIN_API_KEY", "correct-" + "x" * 32)
    with pytest.raises(AdminAuthenticationError):
        verify_admin_api_key(None)
    with pytest.raises(AdminAuthenticationError):
        verify_admin_api_key("wrong-" + "x" * 32)
    verify_admin_api_key("correct-" + "x" * 32)


def test_admin_can_submit_review_and_merge_a_food_stall(submission_repository):
    submissions, discovery = submission_repository
    created = submissions.create(
        FoodSubmissionCreate(
            name="Example Chicken Rice",
            parent_entity_id="hawker:maxwell",
            price_min=4,
            price_max=7,
            cuisine_tags=["Singaporean"],
            dish_tags=["chicken rice"],
            opening_hours=[
                {"day_of_week": 1, "opens_at": "10:00", "closes_at": "19:00"}
            ],
            evidence_notes="Verified with stallholder",
        ),
        actor="base44_admin",
    )

    assert created.status == SubmissionStatus.NEEDS_REVIEW
    assert created.proposed_entity_id is None
    assert created.proposed_fields["evidence_notes"] == "Verified with stallholder"
    assert submissions.list(status=SubmissionStatus.NEEDS_REVIEW)[0].id == created.id

    merged = submissions.approve(created.id, actor="base44_admin")
    assert merged.status == SubmissionStatus.MERGED
    assert merged.proposed_entity_id is not None

    listing = next(
        item
        for item in discovery.search_food_listings()
        if item.entity.id == merged.proposed_entity_id
    )
    assert listing.entity.name == "Example Chicken Rice"
    assert listing.parent.id == "hawker:maxwell"
    assert listing.profile.price_max == 7
    assert listing.tags == {
        "cuisine": ["Singaporean"],
        "dish": ["chicken rice"],
    }
    assert listing.opening_periods[0].opens_at == "10:00"


def test_duplicate_stall_is_not_merged(submission_repository):
    submissions, _ = submission_repository
    proposal = FoodSubmissionCreate(
        name="Duplicate Stall",
        parent_entity_id="hawker:maxwell",
    )
    first = submissions.create(proposal, actor="base44_admin")
    submissions.approve(first.id, actor="base44_admin")
    duplicate = submissions.create(proposal, actor="base44_admin")

    with pytest.raises(ValueError, match="already exists"):
        submissions.approve(duplicate.id, actor="base44_admin")

    assert submissions.get(duplicate.id).status == SubmissionStatus.NEEDS_REVIEW


def test_updates_require_a_valid_food_stall_reference(submission_repository):
    submissions, _ = submission_repository

    with pytest.raises(ValueError, match="food_stall reference"):
        submissions.create(
            FoodSubmissionCreate(
                submission_type=SubmissionType.SUGGEST_UPDATE,
                target_entity_id="hawker:maxwell",
                name="Not a stall",
            ),
            actor="base44_admin",
        )


def test_admin_can_reject_with_an_audit_reason(submission_repository):
    submissions, _ = submission_repository
    created = submissions.create(
        FoodSubmissionCreate(name="Unverified Stall"),
        actor="base44_admin",
    )

    rejected = submissions.reject(
        created.id,
        actor="base44_admin",
        reason="Insufficient evidence",
    )

    assert rejected.status == SubmissionStatus.REJECTED
