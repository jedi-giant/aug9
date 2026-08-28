from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from aug9.core import database
from aug9.discovery.michelin_pilot import (
    MichelinPilotCandidate,
    load_michelin_pilot,
)
from aug9.discovery.models import (
    CommercialStatus,
    DiscoverySource,
    EvidenceDirection,
    FoodEvidence,
    FoodEvidenceDimension,
    FoodEvidenceType,
    SourcePermission,
)
from aug9.discovery.repository import DiscoveryRepository
from aug9.discovery.sfa_food_establishments import SFA_SOURCE_ID


MICHELIN_SOURCE_ID = "michelin_guide_singapore"
MICHELIN_SELECTION_YEAR = 2026
MICHELIN_EVIDENCE_EXPIRY = datetime(2027, 8, 31, 23, 59, 59, tzinfo=UTC)


@dataclass(frozen=True)
class MichelinApprovedMatch:
    michelin_id: str
    entity_id: str


@dataclass(frozen=True)
class MichelinEvidenceSummary:
    run_id: str
    received: int
    upserted: int
    rejected: int


def load_approved_matches(path: Path) -> list[MichelinApprovedMatch]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [
            MichelinApprovedMatch(
                michelin_id=row["michelin_id"].strip(),
                entity_id=row["entity_id"].strip(),
            )
            for row in csv.DictReader(handle)
        ]
    if not rows or len(rows) > 100:
        raise ValueError("Approved Michelin matches must contain between 1 and 100 rows")
    if len({row.michelin_id for row in rows}) != len(rows):
        raise ValueError("Approved Michelin matches contain duplicate Michelin IDs")
    if len({row.entity_id for row in rows}) != len(rows):
        raise ValueError("Approved Michelin matches contain duplicate entity IDs")
    return rows


class MichelinEvidenceImporter:
    def __init__(self, repository: DiscoveryRepository) -> None:
        self.repository = repository

    def run(
        self,
        *,
        pilot_path: Path,
        approvals_path: Path,
    ) -> MichelinEvidenceSummary:
        candidates = {
            candidate.external_id: candidate
            for candidate in load_michelin_pilot(pilot_path)
        }
        approvals = load_approved_matches(approvals_path)
        self._validate_approvals(candidates, approvals)
        self.repository.register_source(
            DiscoverySource(
                id=MICHELIN_SOURCE_ID,
                name="The MICHELIN Guide Singapore",
                permission=SourcePermission.LEGAL_REVIEWED,
                base_url="https://guide.michelin.com/sg/en",
                attribution="The MICHELIN Guide",
                license_name="Use reviewed by Aug9 legal counsel",
            )
        )
        run = self.repository.start_ingestion(MICHELIN_SOURCE_ID)
        upserted = 0
        try:
            for approval in approvals:
                candidate = candidates[approval.michelin_id]
                self.repository.upsert_food_evidence(
                    self._evidence(candidate, approval.entity_id)
                )
                upserted += 1
            self.repository.complete_ingestion(
                run,
                records_received=len(approvals),
                records_upserted=upserted,
            )
            return MichelinEvidenceSummary(run.id, len(approvals), upserted, 0)
        except Exception as exc:
            self.repository.complete_ingestion(
                run,
                records_received=len(approvals),
                records_upserted=upserted,
                error=type(exc).__name__,
            )
            raise

    @staticmethod
    def _validate_approvals(
        candidates: dict[str, MichelinPilotCandidate],
        approvals: list[MichelinApprovedMatch],
    ) -> None:
        unknown = [row.michelin_id for row in approvals if row.michelin_id not in candidates]
        if unknown:
            raise ValueError("Approval references unknown Michelin IDs: " + ", ".join(unknown))

        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        try:
            for approval in approvals:
                cursor.execute(
                    f"""
                    SELECT 1
                    FROM discovery_entities e
                    JOIN discovery_source_records sfa ON sfa.entity_id = e.id
                    WHERE e.id = {p} AND e.status = 'active'
                      AND sfa.source_id = {p}
                    """,
                    (approval.entity_id, SFA_SOURCE_ID),
                )
                if cursor.fetchone() is None:
                    raise ValueError(
                        "Approval does not reference an active SFA entity: "
                        + approval.entity_id
                    )
        finally:
            conn.close()

    @staticmethod
    def _evidence(
        candidate: MichelinPilotCandidate,
        entity_id: str,
    ) -> FoodEvidence:
        observed_at = datetime.fromisoformat(
            candidate.observed_at.replace("Z", "+00:00")
        )
        return FoodEvidence(
            id=f"food-evidence:{MICHELIN_SOURCE_ID}:{candidate.external_id}:2026",
            entity_id=entity_id,
            external_id=f"{candidate.external_id}:bib-gourmand:2026",
            dimension=FoodEvidenceDimension.FOOD_QUALITY,
            evidence_type=FoodEvidenceType.EDITORIAL,
            direction=EvidenceDirection.POSITIVE,
            claim_key="award_or_recognition",
            value={
                "distinction": "Bib Gourmand",
                "selection_year": MICHELIN_SELECTION_YEAR,
            },
            confidence=0.8,
            source_id=MICHELIN_SOURCE_ID,
            source_url=candidate.source_url,
            observed_at=observed_at,
            expires_at=MICHELIN_EVIDENCE_EXPIRY,
            commercial_status=CommercialStatus.ORGANIC,
        )
