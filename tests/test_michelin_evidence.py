from pathlib import Path

import pytest

from aug9.core import database
from aug9.discovery.michelin_evidence import (
    MICHELIN_SOURCE_ID,
    MichelinEvidenceImporter,
    load_approved_matches,
)
from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EntityType,
    FoodEvidenceDimension,
    SourcePermission,
    SourceRecord,
)
from aug9.discovery.repository import DiscoveryRepository
from aug9.discovery.sfa_food_establishments import SFA_SOURCE_ID


PILOT_PATH = Path("data/michelin_singapore_bib_gourmand_pilot_2026.csv")
APPROVALS_PATH = Path(
    "data/michelin_singapore_bib_gourmand_approved_matches_2026.csv"
)


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "michelin-evidence.db")
    database.initialise_database()
    repository = DiscoveryRepository()
    repository.register_source(
        DiscoverySource(
            id=SFA_SOURCE_ID,
            name="SFA",
            permission=SourcePermission.OPEN_DATA,
        )
    )
    for approval in load_approved_matches(APPROVALS_PATH):
        repository.upsert_entity(
            DiscoveryEntity(
                id=approval.entity_id,
                entity_type=EntityType.FOOD_VENUE,
                name=f"Approved {approval.michelin_id}",
            ),
            SourceRecord(
                source_id=SFA_SOURCE_ID,
                external_id=approval.entity_id,
                entity_id=approval.entity_id,
            ),
            [],
        )
    return repository


def test_reviewed_michelin_evidence_import_is_idempotent(repository):
    importer = MichelinEvidenceImporter(repository)

    first = importer.run(pilot_path=PILOT_PATH, approvals_path=APPROVALS_PATH)
    second = importer.run(pilot_path=PILOT_PATH, approvals_path=APPROVALS_PATH)

    assert first.received == 18
    assert first.upserted == 18
    assert second.upserted == 18
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*), MIN(confidence), MAX(confidence) "
        "FROM discovery_food_evidence WHERE source_id = ?",
        (MICHELIN_SOURCE_ID,),
    )
    count, minimum_confidence, maximum_confidence = cursor.fetchone()
    cursor.execute(
        "SELECT value, commercial_status FROM discovery_food_evidence "
        "WHERE source_id = ? LIMIT 1",
        (MICHELIN_SOURCE_ID,),
    )
    value, commercial_status = cursor.fetchone()
    conn.close()

    assert count == 18
    assert minimum_confidence == maximum_confidence == 0.8
    assert '"distinction": "Bib Gourmand"' in value
    assert commercial_status == "organic"
    stored = repository.list_food_evidence(
        load_approved_matches(APPROVALS_PATH)[0].entity_id
    )
    assert stored[0].dimension is FoodEvidenceDimension.FOOD_QUALITY
    assert stored[0].claim_key == "award_or_recognition"
    assert stored[0].expires_at is not None


def test_import_fails_closed_for_unapproved_entity(repository, tmp_path):
    approvals = tmp_path / "invalid-approvals.csv"
    approvals.write_text(
        "michelin_id,entity_id\n501505,food:sfa:missing\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="active SFA entity"):
        MichelinEvidenceImporter(repository).run(
            pilot_path=PILOT_PATH,
            approvals_path=approvals,
        )

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM discovery_food_evidence")
    assert cursor.fetchone()[0] == 0
    conn.close()


def test_approval_manifest_has_unique_entities_and_known_pilot_ids():
    approvals = load_approved_matches(APPROVALS_PATH)

    assert len(approvals) == 18
    assert len({item.michelin_id for item in approvals}) == 18
    assert len({item.entity_id for item in approvals}) == 18
