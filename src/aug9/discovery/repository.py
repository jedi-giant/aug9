import json
from datetime import UTC, datetime
from uuid import uuid4

from aug9.core import database
from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EventProfile,
    FieldProvenance,
    FoodEvidence,
    GooglePlaceLink,
    FoodProfile,
    FoodListing,
    IngestionRun,
    OpeningPeriod,
    RelationshipType,
    SourceRecord,
    SourcePermission,
)


class DiscoveryRepository:
    _ENTITY_COLUMNS = (
        "id, entity_type, name, description, address, postal_code, "
        "latitude, longitude, status, quality_score"
    )

    def register_source(self, source: DiscoverySource) -> None:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"""
            INSERT INTO discovery_sources (
                id, name, permission, base_url, license_name, attribution, active
            ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                permission = excluded.permission,
                base_url = excluded.base_url,
                license_name = excluded.license_name,
                attribution = excluded.attribution,
                active = excluded.active,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                source.id,
                source.name,
                source.permission.value,
                source.base_url,
                source.license_name,
                source.attribution,
                int(source.active),
            ),
        )
        conn.commit()
        conn.close()

    def upsert_entity(
        self,
        entity: DiscoveryEntity,
        record: SourceRecord,
        provenance: list[FieldProvenance],
    ) -> int:
        self._validate_entity_bundle(entity, record, provenance)
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        try:
            self._require_ingestable_source(cursor, record.source_id, p)
            source_record_id = self._upsert_entity_rows(
                cursor, p, entity, record, provenance
            )
            conn.commit()
            return source_record_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def upsert_event_entity(
        self,
        entity: DiscoveryEntity,
        record: SourceRecord,
        provenance: list[FieldProvenance],
        profile: EventProfile,
    ) -> int:
        self._validate_entity_bundle(entity, record, provenance)
        if profile.entity_id != entity.id:
            raise ValueError("Event profile entity_id must match the entity id")
        if profile.source_id != record.source_id:
            raise ValueError("Event profile source_id must match the source record")

        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        try:
            self._require_ingestable_source(cursor, record.source_id, p)
            source_record_id = self._upsert_entity_rows(
                cursor, p, entity, record, provenance
            )
            self._upsert_event_profile_row(cursor, p, profile)
            conn.commit()
            return source_record_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _validate_entity_bundle(
        entity: DiscoveryEntity,
        record: SourceRecord,
        provenance: list[FieldProvenance],
    ) -> None:
        if record.entity_id != entity.id:
            raise ValueError("Source record entity_id must match the entity id")
        if any(item.entity_id != entity.id for item in provenance):
            raise ValueError("Provenance entity_id must match the entity id")
        if any(item.source_id != record.source_id for item in provenance):
            raise ValueError("Provenance source_id must match the source record")

    @staticmethod
    def _upsert_entity_rows(
        cursor,
        p: str,
        entity: DiscoveryEntity,
        record: SourceRecord,
        provenance: list[FieldProvenance],
    ) -> int:
        cursor.execute(
            f"""
                INSERT INTO discovery_entities (
                    id, entity_type, name, description, address, postal_code,
                    latitude, longitude, status, quality_score
                ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                ON CONFLICT(id) DO UPDATE SET
                    entity_type = excluded.entity_type,
                    name = excluded.name,
                    description = excluded.description,
                    address = excluded.address,
                    postal_code = excluded.postal_code,
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    status = excluded.status,
                    quality_score = excluded.quality_score,
                    updated_at = CURRENT_TIMESTAMP
            """,
            (
                    entity.id,
                    entity.entity_type.value,
                    entity.name,
                    entity.description,
                    entity.address,
                    entity.postal_code,
                    entity.latitude,
                    entity.longitude,
                    entity.status,
                    entity.quality_score,
            ),
        )
        cursor.execute(
            f"""
                INSERT INTO discovery_source_records (
                    source_id, external_id, entity_id, source_url, raw_payload,
                    fetched_at, verified_at
                ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
                ON CONFLICT(source_id, external_id) DO UPDATE SET
                    entity_id = excluded.entity_id,
                    source_url = excluded.source_url,
                    raw_payload = excluded.raw_payload,
                    fetched_at = excluded.fetched_at,
                    verified_at = excluded.verified_at
            """,
            (
                    record.source_id,
                    record.external_id,
                    record.entity_id,
                    record.source_url,
                    json.dumps(record.raw_payload, sort_keys=True),
                    record.fetched_at.isoformat(),
                    record.verified_at.isoformat() if record.verified_at else None,
            ),
        )
        cursor.execute(
            f"""
                SELECT id FROM discovery_source_records
                WHERE source_id = {p} AND external_id = {p}
            """,
            (record.source_id, record.external_id),
        )
        source_record_id = cursor.fetchone()[0]

        for item in provenance:
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
                        item.entity_id,
                        item.field_name,
                        item.source_id,
                        source_record_id,
                        json.dumps(item.value, sort_keys=True),
                ),
            )
        return source_record_id

    def start_ingestion(self, source_id: str) -> IngestionRun:
        run = IngestionRun(id=str(uuid4()), source_id=source_id)
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"""
            INSERT INTO discovery_ingestion_runs (
                id, source_id, status, records_received, records_upserted,
                records_rejected, error, started_at, completed_at
            ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
            """,
            (
                run.id,
                run.source_id,
                run.status,
                0,
                0,
                0,
                None,
                run.started_at.isoformat(),
                None,
            ),
        )
        conn.commit()
        conn.close()
        return run

    def complete_ingestion(
        self,
        run: IngestionRun,
        *,
        records_received: int,
        records_upserted: int,
        records_rejected: int = 0,
        error: str | None = None,
    ) -> IngestionRun:
        completed = run.model_copy(
            update={
                "status": "failed" if error else "completed",
                "records_received": records_received,
                "records_upserted": records_upserted,
                "records_rejected": records_rejected,
                "error": error,
                "completed_at": datetime.now(UTC),
            }
        )
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"""
            UPDATE discovery_ingestion_runs SET
                status = {p}, records_received = {p}, records_upserted = {p},
                records_rejected = {p}, error = {p}, completed_at = {p}
            WHERE id = {p}
            """,
            (
                completed.status,
                completed.records_received,
                completed.records_upserted,
                completed.records_rejected,
                completed.error,
                completed.completed_at.isoformat(),
                completed.id,
            ),
        )
        conn.commit()
        conn.close()
        return completed

    def get_entity(self, entity_id: str) -> DiscoveryEntity | None:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"SELECT {self._ENTITY_COLUMNS} FROM discovery_entities WHERE id = {p}",
            (entity_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return self._entity_from_row(row) if row else None

    def upsert_food_profile(
        self,
        profile: FoodProfile,
        *,
        source_id: str,
        tags: dict[str, list[str]] | None = None,
    ) -> None:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        try:
            self._require_ingestable_source(cursor, source_id, p)
            cursor.execute(
                f"""
                INSERT INTO discovery_food_profiles (
                    entity_id, venue_kind, price_min, price_max, currency,
                    dietary_attributes, reservation_url, source_id
                ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                ON CONFLICT(entity_id) DO UPDATE SET
                    venue_kind = excluded.venue_kind,
                    price_min = excluded.price_min,
                    price_max = excluded.price_max,
                    currency = excluded.currency,
                    dietary_attributes = excluded.dietary_attributes,
                    reservation_url = excluded.reservation_url,
                    source_id = excluded.source_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    profile.entity_id,
                    profile.venue_kind,
                    profile.price_min,
                    profile.price_max,
                    profile.currency,
                    json.dumps(profile.dietary_attributes),
                    profile.reservation_url,
                    source_id,
                ),
            )
            if tags is not None:
                cursor.execute(
                    f"DELETE FROM discovery_entity_tags WHERE entity_id = {p}",
                    (profile.entity_id,),
                )
                for category, values in tags.items():
                    for value in values:
                        cursor.execute(
                            f"""
                            INSERT INTO discovery_entity_tags (
                                entity_id, tag, category, source_id
                            ) VALUES ({p}, {p}, {p}, {p})
                            """,
                            (profile.entity_id, value, category, source_id),
                        )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def search_food_listings(self, *, limit: int = 100) -> list[FoodListing]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"""
            SELECT e.id, e.entity_type, e.name, e.description, e.address,
                   e.postal_code, e.latitude, e.longitude, e.status,
                   e.quality_score,
                   fp.venue_kind, fp.price_min, fp.price_max, fp.currency,
                   fp.dietary_attributes, fp.reservation_url, fp.source_id,
                   parent.id, parent.entity_type, parent.name, parent.description,
                   parent.address, parent.postal_code, parent.latitude,
                   parent.longitude, parent.status, parent.quality_score
            FROM discovery_entities e
            JOIN discovery_food_profiles fp ON fp.entity_id = e.id
            LEFT JOIN discovery_entity_relationships rel
              ON rel.child_entity_id = e.id AND rel.relationship_type = 'contains'
            LEFT JOIN discovery_entities parent ON parent.id = rel.parent_entity_id
            WHERE e.status = 'active'
            ORDER BY e.quality_score DESC, e.name ASC
            LIMIT {p}
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        if not rows:
            conn.close()
            return []

        entity_ids = [row[0] for row in rows]
        placeholders = ", ".join(p for _ in entity_ids)
        cursor.execute(
            f"""
            SELECT entity_id, category, tag
            FROM discovery_entity_tags
            WHERE entity_id IN ({placeholders})
            ORDER BY category, tag
            """,
            tuple(entity_ids),
        )
        tags_by_entity: dict[str, dict[str, list[str]]] = {}
        for entity_id, category, tag in cursor.fetchall():
            tags_by_entity.setdefault(entity_id, {}).setdefault(category, []).append(tag)

        cursor.execute(
            f"""
            SELECT entity_id, day_of_week, opens_at, closes_at, source_id
            FROM discovery_opening_hours
            WHERE entity_id IN ({placeholders})
            ORDER BY day_of_week, opens_at
            """,
            tuple(entity_ids),
        )
        hours_by_entity: dict[str, list[OpeningPeriod]] = {}
        for entity_id, day, opens_at, closes_at, source_id in cursor.fetchall():
            hours_by_entity.setdefault(entity_id, []).append(
                OpeningPeriod(
                    entity_id=entity_id,
                    day_of_week=day,
                    opens_at=opens_at,
                    closes_at=closes_at,
                    source_id=source_id,
                )
            )
        conn.close()

        listings = []
        for row in rows:
            entity = self._entity_from_row(row[:10])
            profile = FoodProfile(
                entity_id=entity.id,
                venue_kind=row[10],
                price_min=row[11],
                price_max=row[12],
                currency=row[13],
                dietary_attributes=json.loads(row[14]),
                reservation_url=row[15],
            )
            parent = self._entity_from_row(row[17:27]) if row[17] is not None else None
            listings.append(
                FoodListing(
                    entity=entity,
                    profile=profile,
                    parent=parent,
                    tags=tags_by_entity.get(entity.id, {}),
                    opening_periods=hours_by_entity.get(entity.id, []),
                )
            )
        return listings

    def upsert_food_evidence(self, evidence: FoodEvidence) -> None:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        try:
            self._require_ingestable_source(cursor, evidence.source_id, p)
            cursor.execute(
                f"SELECT 1 FROM discovery_entities WHERE id = {p}",
                (evidence.entity_id,),
            )
            if cursor.fetchone() is None:
                raise ValueError("Food evidence entity does not exist")
            cursor.execute(
                f"""
                INSERT INTO discovery_food_evidence (
                    id, entity_id, external_id, dimension, evidence_type,
                    direction, claim_key, value, dish_name, confidence,
                    source_id, source_url, observed_at, expires_at,
                    commercial_status
                ) VALUES (
                    {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p},
                    {p}, {p}, {p}, {p}, {p}
                )
                ON CONFLICT(source_id, external_id) DO UPDATE SET
                    entity_id = excluded.entity_id,
                    dimension = excluded.dimension,
                    evidence_type = excluded.evidence_type,
                    direction = excluded.direction,
                    claim_key = excluded.claim_key,
                    value = excluded.value,
                    dish_name = excluded.dish_name,
                    confidence = excluded.confidence,
                    source_url = excluded.source_url,
                    observed_at = excluded.observed_at,
                    expires_at = excluded.expires_at,
                    commercial_status = excluded.commercial_status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                self._food_evidence_values(evidence),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_food_evidence(
        self,
        entity_id: str,
        *,
        as_of: datetime | None = None,
        include_expired: bool = False,
        limit: int = 200,
    ) -> list[FoodEvidence]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        conditions = [f"entity_id = {p}"]
        params: list[object] = [entity_id]
        if not include_expired:
            conditions.append(f"(expires_at IS NULL OR expires_at >= {p})")
            params.append((as_of or datetime.now(UTC)).isoformat())
        cursor.execute(
            f"""
            SELECT id, entity_id, external_id, dimension, evidence_type,
                   direction, claim_key, value, dish_name, confidence,
                   source_id, source_url, observed_at, expires_at,
                   commercial_status
            FROM discovery_food_evidence
            WHERE {' AND '.join(conditions)}
            ORDER BY observed_at DESC, id ASC
            LIMIT {p}
            """,
            (*params, limit),
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._food_evidence_from_row(row) for row in rows]

    def upsert_google_place_link(self, link: GooglePlaceLink) -> None:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        try:
            cursor.execute(
                f"SELECT 1 FROM discovery_entities WHERE id = {p}",
                (link.entity_id,),
            )
            if cursor.fetchone() is None:
                raise ValueError("Google place link entity does not exist")
            cursor.execute(
                f"""
                INSERT INTO discovery_google_place_links (
                    entity_id, place_id, match_confidence, match_method,
                    manually_verified, matched_at
                ) VALUES ({p}, {p}, {p}, {p}, {p}, {p})
                ON CONFLICT(entity_id) DO UPDATE SET
                    place_id = excluded.place_id,
                    match_confidence = excluded.match_confidence,
                    match_method = excluded.match_method,
                    manually_verified = excluded.manually_verified,
                    matched_at = excluded.matched_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    link.entity_id,
                    link.place_id,
                    link.match_confidence,
                    link.match_method,
                    int(link.manually_verified),
                    link.matched_at.isoformat(),
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_google_place_links(self, *, limit: int = 500) -> list[GooglePlaceLink]:
        if limit < 1 or limit > 20000:
            raise ValueError("limit must be between 1 and 20000")
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"""
            SELECT entity_id, place_id, match_confidence, match_method,
                   matched_at, manually_verified
            FROM discovery_google_place_links
            ORDER BY entity_id
            LIMIT {p}
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            GooglePlaceLink(
                entity_id=row[0],
                place_id=row[1],
                match_confidence=row[2],
                match_method=row[3],
                matched_at=row[4],
                manually_verified=bool(row[5]),
            )
            for row in rows
        ]

    def save_google_place_link_batch(
        self,
        links: list[GooglePlaceLink],
        attempts: list[tuple[str, str]],
    ) -> None:
        """Persist one linker batch using a single database transaction."""
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        try:
            for link in links:
                cursor.execute(
                    f"""
                    INSERT INTO discovery_google_place_links (
                        entity_id, place_id, match_confidence, match_method,
                        manually_verified, matched_at
                    ) VALUES ({p}, {p}, {p}, {p}, {p}, {p})
                    ON CONFLICT(entity_id) DO UPDATE SET
                        place_id = excluded.place_id,
                        match_confidence = excluded.match_confidence,
                        match_method = excluded.match_method,
                        manually_verified = excluded.manually_verified,
                        matched_at = excluded.matched_at,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        link.entity_id,
                        link.place_id,
                        link.match_confidence,
                        link.match_method,
                        int(link.manually_verified),
                        link.matched_at.isoformat(),
                    ),
                )
            attempted_at = datetime.now(UTC).isoformat()
            for entity_id, outcome in attempts:
                cursor.execute(
                    f"""
                    INSERT INTO discovery_google_place_link_attempts (
                        entity_id, outcome, attempted_at
                    ) VALUES ({p}, {p}, {p})
                    ON CONFLICT(entity_id) DO UPDATE SET
                        outcome = excluded.outcome,
                        attempted_at = excluded.attempted_at
                    """,
                    (entity_id, outcome, attempted_at),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _food_evidence_values(evidence: FoodEvidence) -> tuple:
        return (
            evidence.id,
            evidence.entity_id,
            evidence.external_id,
            evidence.dimension.value,
            evidence.evidence_type.value,
            evidence.direction.value,
            evidence.claim_key,
            json.dumps(evidence.value, sort_keys=True),
            evidence.dish_name,
            evidence.confidence,
            evidence.source_id,
            evidence.source_url,
            evidence.observed_at.isoformat(),
            evidence.expires_at.isoformat() if evidence.expires_at else None,
            evidence.commercial_status.value,
        )

    @staticmethod
    def _food_evidence_from_row(row) -> FoodEvidence:
        return FoodEvidence(
            id=row[0],
            entity_id=row[1],
            external_id=row[2],
            dimension=row[3],
            evidence_type=row[4],
            direction=row[5],
            claim_key=row[6],
            value=json.loads(row[7]),
            dish_name=row[8],
            confidence=row[9],
            source_id=row[10],
            source_url=row[11],
            observed_at=row[12],
            expires_at=row[13],
            commercial_status=row[14],
        )

    def add_relationship(
        self,
        parent_entity_id: str,
        child_entity_id: str,
        relationship_type: RelationshipType,
        *,
        source_id: str,
    ) -> None:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        try:
            self._require_ingestable_source(cursor, source_id, p)
            cursor.execute(
                f"""
                INSERT INTO discovery_entity_relationships (
                    parent_entity_id, child_entity_id, relationship_type, source_id
                ) VALUES ({p}, {p}, {p}, {p})
                ON CONFLICT(parent_entity_id, child_entity_id, relationship_type)
                DO UPDATE SET source_id = excluded.source_id
                """,
                (
                    parent_entity_id,
                    child_entity_id,
                    relationship_type.value,
                    source_id,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def upsert_event_profile(self, profile: EventProfile) -> None:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        try:
            self._require_ingestable_source(cursor, profile.source_id, p)
            self._upsert_event_profile_row(cursor, p, profile)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _upsert_event_profile_row(cursor, p: str, profile: EventProfile) -> None:
        cursor.execute(
            f"""
                INSERT INTO discovery_event_profiles (
                    entity_id, starts_at, ends_at, category, organiser,
                    ticketed, price_min, currency, booking_url, source_url,
                    source_id
                ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                ON CONFLICT(entity_id) DO UPDATE SET
                    starts_at = excluded.starts_at,
                    ends_at = excluded.ends_at,
                    category = excluded.category,
                    organiser = excluded.organiser,
                    ticketed = excluded.ticketed,
                    price_min = excluded.price_min,
                    currency = excluded.currency,
                    booking_url = excluded.booking_url,
                    source_url = excluded.source_url,
                    source_id = excluded.source_id,
                    updated_at = CURRENT_TIMESTAMP
            """,
            (
                profile.entity_id,
                profile.starts_at.isoformat(),
                profile.ends_at.isoformat() if profile.ends_at else None,
                profile.category,
                profile.organiser,
                int(profile.ticketed) if profile.ticketed is not None else None,
                profile.price_min,
                profile.currency,
                profile.booking_url,
                profile.source_url,
                profile.source_id,
            ),
        )

    def search_events(
        self,
        *,
        query: str | None = None,
        starts_after: datetime | None = None,
        starts_before: datetime | None = None,
        category: str | None = None,
        limit: int = 12,
    ) -> list[tuple[DiscoveryEntity, EventProfile]]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        filters = ["e.status = 'active'", "e.entity_type = 'event'"]
        parameters: list[object] = []
        if query:
            filters.append(f"(LOWER(e.name) LIKE {p} OR LOWER(e.address) LIKE {p})")
            value = f"%{query.casefold().strip()}%"
            parameters.extend((value, value))
        if starts_after:
            filters.append(f"COALESCE(ep.ends_at, ep.starts_at) >= {p}")
            parameters.append(starts_after.isoformat())
        if starts_before:
            filters.append(f"ep.starts_at < {p}")
            parameters.append(starts_before.isoformat())
        if category:
            filters.append(f"LOWER(ep.category) = {p}")
            parameters.append(category.casefold().strip())
        parameters.append(limit)
        cursor.execute(
            f"""
            SELECT {', '.join('e.' + item.strip() for item in self._ENTITY_COLUMNS.split(','))},
                   ep.starts_at, ep.ends_at, ep.category, ep.organiser,
                   ep.ticketed, ep.price_min, ep.currency, ep.booking_url,
                   ep.source_url, ep.source_id
            FROM discovery_entities e
            JOIN discovery_event_profiles ep ON ep.entity_id = e.id
            WHERE {' AND '.join(filters)}
            ORDER BY ep.starts_at ASC, e.quality_score DESC
            LIMIT {p}
            """,
            tuple(parameters),
        )
        rows = cursor.fetchall()
        conn.close()
        results = []
        for row in rows:
            entity = self._entity_from_row(row[:10])
            profile = EventProfile(
                entity_id=entity.id,
                starts_at=row[10],
                ends_at=row[11],
                category=row[12],
                organiser=row[13],
                ticketed=bool(row[14]) if row[14] is not None else None,
                price_min=row[15],
                currency=row[16],
                booking_url=row[17],
                source_url=row[18],
                source_id=row[19],
            )
            results.append((entity, profile))
        return results

    def replace_opening_hours(
        self,
        entity_id: str,
        periods: list[OpeningPeriod],
        *,
        source_id: str,
    ) -> None:
        if any(item.entity_id != entity_id for item in periods):
            raise ValueError("Opening-period entity IDs must match")
        if any(item.source_id != source_id for item in periods):
            raise ValueError("Opening-period source IDs must match")
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        try:
            self._require_ingestable_source(cursor, source_id, p)
            cursor.execute(
                f"""
                DELETE FROM discovery_opening_hours
                WHERE entity_id = {p} AND source_id = {p}
                """,
                (entity_id, source_id),
            )
            for period in periods:
                cursor.execute(
                    f"""
                    INSERT INTO discovery_opening_hours (
                        entity_id, day_of_week, opens_at, closes_at, source_id
                    ) VALUES ({p}, {p}, {p}, {p}, {p})
                    """,
                    (
                        entity_id,
                        period.day_of_week,
                        period.opens_at,
                        period.closes_at,
                        source_id,
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _require_ingestable_source(cursor, source_id: str, p: str) -> None:
        cursor.execute(
            f"SELECT permission, active FROM discovery_sources WHERE id = {p}",
            (source_id,),
        )
        row = cursor.fetchone()
        allowed = {
            SourcePermission.OPEN_DATA.value,
            SourcePermission.USER_PROVIDED.value,
            SourcePermission.LICENSED_PARTNER.value,
            SourcePermission.LEGAL_REVIEWED.value,
        }
        if row is None:
            raise ValueError(f"Unknown discovery source: {source_id}")
        if not row[1]:
            raise ValueError(f"Discovery source '{source_id}' is inactive")
        if row[0] not in allowed:
            raise ValueError(
                f"Source permission '{row[0]}' does not allow ingestion"
            )

    def search_entities(
        self,
        query: str | None = None,
        *,
        entity_type: str | None = None,
        limit: int = 20,
    ) -> list[DiscoveryEntity]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        filters = ["status = 'active'"]
        parameters: list[object] = []
        if query:
            filters.append(f"LOWER(name) LIKE {p}")
            parameters.append(f"%{query.casefold().strip()}%")
        if entity_type:
            filters.append(f"entity_type = {p}")
            parameters.append(entity_type)
        parameters.append(limit)
        cursor.execute(
            f"""
            SELECT {self._ENTITY_COLUMNS}
            FROM discovery_entities
            WHERE {' AND '.join(filters)}
            ORDER BY quality_score DESC, name ASC
            LIMIT {p}
            """,
            tuple(parameters),
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._entity_from_row(row) for row in rows]

    def archive_expired_events(self, *, now: datetime | None = None) -> int:
        cutoff = now or datetime.now(UTC)
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"""
            UPDATE discovery_entities
            SET status = 'archived', updated_at = CURRENT_TIMESTAMP
            WHERE entity_type = 'event'
              AND status = 'active'
              AND id IN (
                  SELECT entity_id FROM discovery_event_profiles
                  WHERE ends_at IS NOT NULL AND ends_at < {p}
              )
            """,
            (cutoff.isoformat(),),
        )
        archived = cursor.rowcount
        conn.commit()
        conn.close()
        return archived

    @staticmethod
    def _entity_from_row(row) -> DiscoveryEntity:
        return DiscoveryEntity(
            id=row[0],
            entity_type=row[1],
            name=row[2],
            description=row[3],
            address=row[4],
            postal_code=row[5],
            latitude=row[6],
            longitude=row[7],
            status=row[8],
            quality_score=row[9],
        )
