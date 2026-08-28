import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from aug9.core import database


ADMIN_SOURCE_ID = "aug9_admin"


class SubmissionStatus(StrEnum):
    SUBMITTED = "submitted"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    MERGED = "merged"


class SubmissionType(StrEnum):
    ADD_STALL = "add_stall"
    SUGGEST_UPDATE = "suggest_update"
    REPORT_CLOSURE = "report_closure"


class ProposedOpeningPeriod(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    opens_at: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    closes_at: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class FoodSubmissionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    submission_type: SubmissionType = SubmissionType.ADD_STALL
    target_entity_id: str | None = Field(default=None, max_length=160)
    name: str = Field(min_length=2, max_length=200)
    parent_entity_id: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    address: str | None = Field(default=None, max_length=300)
    postal_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    latitude: float | None = Field(default=None, ge=1.1, le=1.5)
    longitude: float | None = Field(default=None, ge=103.6, le=104.1)
    venue_kind: str = Field(default="hawker_stall", max_length=80)
    price_min: float | None = Field(default=None, ge=0, le=1000)
    price_max: float | None = Field(default=None, ge=0, le=1000)
    dietary_attributes: list[str] = Field(default_factory=list, max_length=20)
    cuisine_tags: list[str] = Field(default_factory=list, max_length=20)
    dish_tags: list[str] = Field(default_factory=list, max_length=30)
    opening_hours: list[ProposedOpeningPeriod] = Field(default_factory=list, max_length=28)
    evidence_url: HttpUrl | None = None
    evidence_notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_submission(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if (
            self.price_min is not None
            and self.price_max is not None
            and self.price_max < self.price_min
        ):
            raise ValueError("price_max must be greater than or equal to price_min")
        if self.submission_type != SubmissionType.ADD_STALL and not self.target_entity_id:
            raise ValueError("target_entity_id is required for updates and closures")
        return self

    def proposed_fields(self) -> dict[str, object]:
        values = self.model_dump(
            exclude={"submission_type", "target_entity_id", "evidence_url", "evidence_notes"},
            mode="json",
        )
        return {key: value for key, value in values.items() if value not in (None, [], "")}


class FoodSubmission(BaseModel):
    id: str
    submission_type: SubmissionType
    target_entity_id: str | None = None
    status: SubmissionStatus
    submitted_by: str
    proposed_entity_id: str | None = None
    proposed_fields: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None = None


class FoodSubmissionRepository:
    def create(self, proposal: FoodSubmissionCreate, *, actor: str) -> FoodSubmission:
        submission_id = str(uuid4())
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        try:
            self._validate_references(cursor, p, proposal)
            cursor.execute(
                f"""
                INSERT INTO discovery_submissions (
                    id, submission_type, entity_type, target_entity_id,
                    status, submitted_by
                ) VALUES ({p}, {p}, 'food_stall', {p}, {p}, {p})
                """,
                (
                    submission_id,
                    proposal.submission_type.value,
                    proposal.target_entity_id,
                    SubmissionStatus.NEEDS_REVIEW.value,
                    actor,
                ),
            )
            for field_name, value in proposal.proposed_fields().items():
                cursor.execute(
                    f"""
                    INSERT INTO submission_field_proposals (
                        submission_id, field_name, proposed_value
                    ) VALUES ({p}, {p}, {p})
                    """,
                    (submission_id, field_name, json.dumps(value, sort_keys=True)),
                )
            if proposal.evidence_url or proposal.evidence_notes:
                cursor.execute(
                    f"""
                    INSERT INTO submission_evidence (
                        submission_id, evidence_type, reference_url, notes
                    ) VALUES ({p}, 'admin_reference', {p}, {p})
                    """,
                    (
                        submission_id,
                        str(proposal.evidence_url) if proposal.evidence_url else None,
                        proposal.evidence_notes,
                    ),
                )
            self._record_event(cursor, p, submission_id, "submitted", actor, None)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get(submission_id)

    def list(self, *, status: SubmissionStatus | None = None, limit: int = 50) -> list[FoodSubmission]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        where = f"WHERE status = {p}" if status else ""
        params: tuple[object, ...] = (status.value, limit) if status else (limit,)
        cursor.execute(
            f"""
            SELECT id, submission_type, target_entity_id, status, submitted_by,
                   proposed_entity_id, created_at, updated_at, reviewed_at
            FROM discovery_submissions {where}
            ORDER BY created_at DESC LIMIT {p}
            """,
            params,
        )
        submissions = [self._from_row(row, {}) for row in cursor.fetchall()]
        for submission in submissions:
            submission.proposed_fields = self._load_fields(cursor, p, submission.id)
        conn.close()
        return submissions

    def get(self, submission_id: str) -> FoodSubmission:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"""
            SELECT id, submission_type, target_entity_id, status, submitted_by,
                   proposed_entity_id, created_at, updated_at, reviewed_at
            FROM discovery_submissions WHERE id = {p}
            """,
            (submission_id,),
        )
        row = cursor.fetchone()
        if row is None:
            conn.close()
            raise KeyError(submission_id)
        fields = self._load_fields(cursor, p, submission_id)
        conn.close()
        return self._from_row(row, fields)

    def approve(self, submission_id: str, *, actor: str) -> FoodSubmission:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        try:
            cursor.execute(
                f"SELECT submission_type, target_entity_id, status FROM discovery_submissions WHERE id = {p}",
                (submission_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError(submission_id)
            submission_type, target_entity_id, status = row
            if status not in {SubmissionStatus.NEEDS_REVIEW.value, SubmissionStatus.SUBMITTED.value}:
                raise ValueError(f"Submission cannot be approved from status '{status}'")
            fields = self._load_fields(cursor, p, submission_id)
            entity_id = target_entity_id
            if submission_type == SubmissionType.ADD_STALL.value:
                entity_id = f"stall:{uuid4()}"
                self._insert_new_stall(cursor, p, entity_id, submission_id, fields)
            elif submission_type == SubmissionType.REPORT_CLOSURE.value:
                cursor.execute(
                    f"UPDATE discovery_entities SET status = 'archived', updated_at = CURRENT_TIMESTAMP WHERE id = {p}",
                    (entity_id,),
                )
                if cursor.rowcount != 1:
                    raise ValueError("Target food stall does not exist")
            else:
                self._update_stall(cursor, p, entity_id, fields)
            cursor.execute(
                f"""
                UPDATE discovery_submissions SET status = {p}, proposed_entity_id = {p},
                    reviewed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = {p}
                """,
                (SubmissionStatus.MERGED.value, entity_id, submission_id),
            )
            self._record_event(cursor, p, submission_id, "approved_and_merged", actor, None)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get(submission_id)

    def reject(self, submission_id: str, *, actor: str, reason: str) -> FoodSubmission:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        try:
            cursor.execute(
                f"""
                UPDATE discovery_submissions SET status = {p}, reviewed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = {p} AND status IN ('submitted', 'needs_review')
                """,
                (SubmissionStatus.REJECTED.value, submission_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Submission is missing or no longer reviewable")
            self._record_event(cursor, p, submission_id, "rejected", actor, reason)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get(submission_id)

    @staticmethod
    def _validate_references(cursor, p: str, proposal: FoodSubmissionCreate) -> None:
        for entity_id, expected_type in (
            (proposal.parent_entity_id, "hawker_centre"),
            (proposal.target_entity_id, "food_stall"),
        ):
            if not entity_id:
                continue
            cursor.execute(
                f"SELECT entity_type FROM discovery_entities WHERE id = {p} AND status = 'active'",
                (entity_id,),
            )
            row = cursor.fetchone()
            if row is None or row[0] != expected_type:
                raise ValueError(f"Invalid {expected_type} reference: {entity_id}")

    @staticmethod
    def _load_fields(cursor, p: str, submission_id: str) -> dict[str, object]:
        cursor.execute(
            f"SELECT field_name, proposed_value FROM submission_field_proposals WHERE submission_id = {p}",
            (submission_id,),
        )
        return {name: json.loads(value) for name, value in cursor.fetchall()}

    @staticmethod
    def _from_row(row, fields: dict[str, object]) -> FoodSubmission:
        return FoodSubmission(
            id=row[0], submission_type=row[1], target_entity_id=row[2], status=row[3],
            submitted_by=row[4], proposed_entity_id=row[5], created_at=row[6],
            updated_at=row[7], reviewed_at=row[8], proposed_fields=fields,
        )

    @staticmethod
    def _record_event(cursor, p: str, submission_id: str, action: str, actor: str, reason: str | None) -> None:
        cursor.execute(
            f"INSERT INTO submission_moderation_events (submission_id, action, actor, reason) VALUES ({p}, {p}, {p}, {p})",
            (submission_id, action, actor, reason),
        )

    @staticmethod
    def _insert_new_stall(cursor, p: str, entity_id: str, submission_id: str, fields: dict[str, object]) -> None:
        name = str(fields["name"])
        parent_id = fields.get("parent_entity_id")
        cursor.execute(
            f"""
            SELECT e.id FROM discovery_entities e
            LEFT JOIN discovery_entity_relationships r ON r.child_entity_id = e.id
                AND r.relationship_type = 'contains'
            WHERE e.entity_type = 'food_stall' AND e.status = 'active'
              AND LOWER(e.name) = {p} AND COALESCE(r.parent_entity_id, '') = COALESCE({p}, '')
            LIMIT 1
            """,
            (name.casefold(), parent_id),
        )
        if cursor.fetchone():
            raise ValueError("A matching active food stall already exists")
        cursor.execute(
            f"""
            INSERT INTO discovery_entities (
                id, entity_type, name, description, address, postal_code,
                latitude, longitude, status, quality_score
            ) VALUES ({p}, 'food_stall', {p}, {p}, {p}, {p}, {p}, {p}, 'active', 0.7)
            """,
            (entity_id, name, fields.get("description"), fields.get("address"),
             fields.get("postal_code"), fields.get("latitude"), fields.get("longitude")),
        )
        cursor.execute(
            f"""
            INSERT INTO discovery_source_records (
                source_id, external_id, entity_id, raw_payload, fetched_at, verified_at
            ) VALUES ({p}, {p}, {p}, {p}, {p}, {p})
            """,
            (ADMIN_SOURCE_ID, submission_id, entity_id, json.dumps(fields, sort_keys=True),
             datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat()),
        )
        cursor.execute(
            f"""
            SELECT id FROM discovery_source_records
            WHERE source_id = {p} AND external_id = {p}
            """,
            (ADMIN_SOURCE_ID, submission_id),
        )
        source_record_id = cursor.fetchone()[0]
        for field_name in (
            "name", "description", "address", "postal_code", "latitude", "longitude"
        ):
            if field_name not in fields:
                continue
            cursor.execute(
                f"""
                INSERT INTO discovery_field_provenance (
                    entity_id, field_name, source_id, source_record_id, value
                ) VALUES ({p}, {p}, {p}, {p}, {p})
                ON CONFLICT(entity_id, field_name, source_id) DO UPDATE SET
                    source_record_id = excluded.source_record_id,
                    value = excluded.value,
                    created_at = CURRENT_TIMESTAMP
                """,
                (
                    entity_id,
                    field_name,
                    ADMIN_SOURCE_ID,
                    source_record_id,
                    json.dumps(fields[field_name], sort_keys=True),
                ),
            )
        FoodSubmissionRepository._upsert_profile(cursor, p, entity_id, fields)
        if parent_id:
            cursor.execute(
                f"""
                INSERT INTO discovery_entity_relationships (
                    parent_entity_id, child_entity_id, relationship_type, source_id
                ) VALUES ({p}, {p}, 'contains', {p})
                """,
                (parent_id, entity_id, ADMIN_SOURCE_ID),
            )
        FoodSubmissionRepository._replace_detail_rows(cursor, p, entity_id, fields)

    @staticmethod
    def _update_stall(cursor, p: str, entity_id: str | None, fields: dict[str, object]) -> None:
        if not entity_id:
            raise ValueError("Target food stall is required")
        allowed = {"name", "description", "address", "postal_code", "latitude", "longitude"}
        updates = [(key, value) for key, value in fields.items() if key in allowed]
        if updates:
            assignments = ", ".join(f"{key} = {p}" for key, _ in updates)
            cursor.execute(
                f"UPDATE discovery_entities SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = {p} AND entity_type = 'food_stall'",
                tuple(value for _, value in updates) + (entity_id,),
            )
            if cursor.rowcount != 1:
                raise ValueError("Target food stall does not exist")
        profile_fields = {
            "venue_kind", "price_min", "price_max", "dietary_attributes"
        }
        if profile_fields.intersection(fields):
            FoodSubmissionRepository._upsert_profile(cursor, p, entity_id, fields)
        FoodSubmissionRepository._replace_detail_rows(cursor, p, entity_id, fields)

    @staticmethod
    def _upsert_profile(cursor, p: str, entity_id: str, fields: dict[str, object]) -> None:
        cursor.execute(
            f"""
            SELECT venue_kind, price_min, price_max, dietary_attributes
            FROM discovery_food_profiles WHERE entity_id = {p}
            """,
            (entity_id,),
        )
        existing = cursor.fetchone()
        existing_dietary = json.loads(existing[3]) if existing else []
        cursor.execute(
            f"""
            INSERT INTO discovery_food_profiles (
                entity_id, venue_kind, price_min, price_max, currency,
                dietary_attributes, source_id
            ) VALUES ({p}, {p}, {p}, {p}, 'SGD', {p}, {p})
            ON CONFLICT(entity_id) DO UPDATE SET
                venue_kind = COALESCE(excluded.venue_kind, discovery_food_profiles.venue_kind),
                price_min = COALESCE(excluded.price_min, discovery_food_profiles.price_min),
                price_max = COALESCE(excluded.price_max, discovery_food_profiles.price_max),
                dietary_attributes = excluded.dietary_attributes,
                source_id = excluded.source_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                entity_id,
                fields.get("venue_kind", existing[0] if existing else "hawker_stall"),
                fields.get("price_min", existing[1] if existing else None),
                fields.get("price_max", existing[2] if existing else None),
                json.dumps(fields.get("dietary_attributes", existing_dietary)),
                ADMIN_SOURCE_ID,
            ),
        )

    @staticmethod
    def _replace_detail_rows(cursor, p: str, entity_id: str, fields: dict[str, object]) -> None:
        tag_fields = {"cuisine_tags": "cuisine", "dish_tags": "dish"}
        for field_name, category in tag_fields.items():
            if field_name not in fields:
                continue
            cursor.execute(f"DELETE FROM discovery_entity_tags WHERE entity_id = {p} AND category = {p}", (entity_id, category))
            for tag in fields[field_name]:
                normalized = re.sub(r"\s+", " ", str(tag)).strip()[:100]
                if normalized:
                    cursor.execute(
                        f"INSERT INTO discovery_entity_tags (entity_id, tag, category, source_id) VALUES ({p}, {p}, {p}, {p})",
                        (entity_id, normalized, category, ADMIN_SOURCE_ID),
                    )
        if "opening_hours" in fields:
            cursor.execute(f"DELETE FROM discovery_opening_hours WHERE entity_id = {p} AND source_id = {p}", (entity_id, ADMIN_SOURCE_ID))
            for period in fields["opening_hours"]:
                cursor.execute(
                    f"""
                    INSERT INTO discovery_opening_hours (
                        entity_id, day_of_week, opens_at, closes_at, source_id
                    ) VALUES ({p}, {p}, {p}, {p}, {p})
                    """,
                    (entity_id, period["day_of_week"], period["opens_at"], period["closes_at"], ADMIN_SOURCE_ID),
                )
