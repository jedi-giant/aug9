import json
from datetime import UTC, datetime
from uuid import uuid4

from aug9.core import database
from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    EventProfile,
    FieldProvenance,
    FoodProfile,
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
        if record.entity_id != entity.id:
            raise ValueError("Source record entity_id must match the entity id")
        if any(item.entity_id != entity.id for item in provenance):
            raise ValueError("Provenance entity_id must match the entity id")
        if any(item.source_id != record.source_id for item in provenance):
            raise ValueError("Provenance source_id must match the source record")

        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        try:
            cursor.execute(
                f"SELECT permission FROM discovery_sources WHERE id = {p}",
                (record.source_id,),
            )
            source_row = cursor.fetchone()
            if source_row is None:
                raise ValueError(f"Unknown discovery source: {record.source_id}")
            ingestable = {
                SourcePermission.OPEN_DATA.value,
                SourcePermission.LICENSED_PARTNER.value,
            }
            if source_row[0] not in ingestable:
                raise ValueError(
                    f"Source permission '{source_row[0]}' does not allow ingestion"
                )

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
            conn.commit()
            return source_record_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

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
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

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
            f"SELECT permission FROM discovery_sources WHERE id = {p}",
            (source_id,),
        )
        row = cursor.fetchone()
        allowed = {
            SourcePermission.OPEN_DATA.value,
            SourcePermission.LICENSED_PARTNER.value,
        }
        if row is None:
            raise ValueError(f"Unknown discovery source: {source_id}")
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
