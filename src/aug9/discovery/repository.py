import json
from datetime import UTC, datetime
from uuid import uuid4

from aug9.core import database
from aug9.discovery.models import (
    DiscoveryEntity,
    DiscoverySource,
    FieldProvenance,
    IngestionRun,
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
