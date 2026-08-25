def initialise_discovery_schema(cursor, *, postgres: bool) -> None:
    id_column = "BIGSERIAL PRIMARY KEY" if postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    reference_id_column = "BIGINT" if postgres else "INTEGER"

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS discovery_sources (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            permission TEXT NOT NULL,
            base_url TEXT,
            license_name TEXT,
            attribution TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS discovery_entities (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            address TEXT,
            postal_code TEXT,
            latitude REAL,
            longitude REAL,
            status TEXT NOT NULL DEFAULT 'active',
            quality_score REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS discovery_source_records (
            id {id_column},
            source_id TEXT NOT NULL,
            external_id TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            source_url TEXT,
            raw_payload TEXT NOT NULL DEFAULT '{{}}',
            fetched_at TIMESTAMP NOT NULL,
            verified_at TIMESTAMP,
            UNIQUE(source_id, external_id),
            FOREIGN KEY(source_id) REFERENCES discovery_sources(id),
            FOREIGN KEY(entity_id) REFERENCES discovery_entities(id)
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS discovery_field_provenance (
            id {id_column},
            entity_id TEXT NOT NULL,
            field_name TEXT NOT NULL,
            source_id TEXT NOT NULL,
            source_record_id {reference_id_column},
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(entity_id, field_name, source_id),
            FOREIGN KEY(entity_id) REFERENCES discovery_entities(id),
            FOREIGN KEY(source_id) REFERENCES discovery_sources(id),
            FOREIGN KEY(source_record_id) REFERENCES discovery_source_records(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS discovery_ingestion_runs (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            status TEXT NOT NULL,
            records_received INTEGER NOT NULL DEFAULT 0,
            records_upserted INTEGER NOT NULL DEFAULT 0,
            records_rejected INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            started_at TIMESTAMP NOT NULL,
            completed_at TIMESTAMP,
            FOREIGN KEY(source_id) REFERENCES discovery_sources(id)
        )
        """
    )
