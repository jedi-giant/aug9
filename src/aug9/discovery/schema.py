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
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS discovery_entity_relationships (
            parent_entity_id TEXT NOT NULL,
            child_entity_id TEXT NOT NULL,
            relationship_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(parent_entity_id, child_entity_id, relationship_type),
            FOREIGN KEY(parent_entity_id) REFERENCES discovery_entities(id),
            FOREIGN KEY(child_entity_id) REFERENCES discovery_entities(id),
            FOREIGN KEY(source_id) REFERENCES discovery_sources(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS discovery_food_profiles (
            entity_id TEXT PRIMARY KEY,
            venue_kind TEXT NOT NULL,
            price_min REAL,
            price_max REAL,
            currency TEXT NOT NULL DEFAULT 'SGD',
            dietary_attributes TEXT NOT NULL DEFAULT '[]',
            reservation_url TEXT,
            source_id TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(entity_id) REFERENCES discovery_entities(id),
            FOREIGN KEY(source_id) REFERENCES discovery_sources(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS discovery_food_safety_profiles (
            entity_id TEXT PRIMARY KEY,
            licence_number TEXT NOT NULL UNIQUE,
            safe_grade TEXT NOT NULL,
            business_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            observed_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(entity_id) REFERENCES discovery_entities(id),
            FOREIGN KEY(source_id) REFERENCES discovery_sources(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS discovery_food_evidence (
            id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL,
            external_id TEXT NOT NULL,
            dimension TEXT NOT NULL,
            evidence_type TEXT NOT NULL,
            direction TEXT NOT NULL,
            claim_key TEXT NOT NULL,
            value TEXT NOT NULL,
            dish_name TEXT,
            confidence REAL NOT NULL,
            source_id TEXT NOT NULL,
            source_url TEXT,
            observed_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP,
            commercial_status TEXT NOT NULL DEFAULT 'organic',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_id, external_id),
            FOREIGN KEY(entity_id) REFERENCES discovery_entities(id),
            FOREIGN KEY(source_id) REFERENCES discovery_sources(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS discovery_google_place_links (
            entity_id TEXT PRIMARY KEY,
            place_id TEXT NOT NULL UNIQUE,
            match_confidence REAL NOT NULL,
            match_method TEXT NOT NULL,
            manually_verified INTEGER NOT NULL DEFAULT 0,
            matched_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(entity_id) REFERENCES discovery_entities(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS discovery_google_place_link_attempts (
            entity_id TEXT PRIMARY KEY,
            outcome TEXT NOT NULL,
            attempted_at TIMESTAMP NOT NULL,
            FOREIGN KEY(entity_id) REFERENCES discovery_entities(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS discovery_food_candidates (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            external_id TEXT NOT NULL,
            name TEXT NOT NULL,
            address_text TEXT,
            opening_hours_text TEXT,
            dish_tags TEXT NOT NULL DEFAULT '[]',
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'staged',
            quarantine_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_id, external_id),
            FOREIGN KEY(source_id) REFERENCES discovery_sources(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS discovery_submissions (
            id TEXT PRIMARY KEY,
            submission_type TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            target_entity_id TEXT,
            status TEXT NOT NULL DEFAULT 'submitted',
            submitted_by TEXT NOT NULL,
            proposed_entity_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS submission_field_proposals (
            id {id_column},
            submission_id TEXT NOT NULL,
            field_name TEXT NOT NULL,
            proposed_value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(submission_id, field_name),
            FOREIGN KEY(submission_id) REFERENCES discovery_submissions(id)
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS submission_evidence (
            id {id_column},
            submission_id TEXT NOT NULL,
            evidence_type TEXT NOT NULL,
            reference_url TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(submission_id) REFERENCES discovery_submissions(id)
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS submission_moderation_events (
            id {id_column},
            submission_id TEXT NOT NULL,
            action TEXT NOT NULL,
            actor TEXT NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(submission_id) REFERENCES discovery_submissions(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS discovery_submissions_status_idx
        ON discovery_submissions(status, created_at)
        """
    )
    cursor.execute(
        """
        INSERT INTO discovery_sources (
            id, name, permission, attribution, active
        ) VALUES (
            'aug9_admin', 'Aug9 administrator submissions',
            'legal_reviewed', 'Aug9 administrator verified', 1
        )
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            permission = excluded.permission,
            attribution = excluded.attribution,
            active = excluded.active,
            updated_at = CURRENT_TIMESTAMP
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS discovery_entity_tags (
            entity_id TEXT NOT NULL,
            tag TEXT NOT NULL,
            category TEXT NOT NULL,
            source_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(entity_id, tag, category),
            FOREIGN KEY(entity_id) REFERENCES discovery_entities(id),
            FOREIGN KEY(source_id) REFERENCES discovery_sources(id)
        )
        """
    )
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS discovery_opening_hours (
            id {id_column},
            entity_id TEXT NOT NULL,
            day_of_week INTEGER NOT NULL,
            opens_at TEXT NOT NULL,
            closes_at TEXT NOT NULL,
            source_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(entity_id, day_of_week, opens_at, closes_at, source_id),
            FOREIGN KEY(entity_id) REFERENCES discovery_entities(id),
            FOREIGN KEY(source_id) REFERENCES discovery_sources(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS market_statistics (
            source_id TEXT NOT NULL,
            dataset_id TEXT NOT NULL,
            external_id TEXT NOT NULL,
            metric TEXT NOT NULL,
            category TEXT,
            period TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT NOT NULL,
            geography TEXT NOT NULL,
            raw_payload TEXT NOT NULL DEFAULT '{}',
            fetched_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(source_id, dataset_id, external_id),
            FOREIGN KEY(source_id) REFERENCES discovery_sources(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS discovery_hotel_profiles (
            entity_id TEXT PRIMARY KEY,
            room_count INTEGER,
            source_updated_at TEXT,
            source_id TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(entity_id) REFERENCES discovery_entities(id),
            FOREIGN KEY(source_id) REFERENCES discovery_sources(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS discovery_event_profiles (
            entity_id TEXT PRIMARY KEY,
            starts_at TIMESTAMP NOT NULL,
            ends_at TIMESTAMP,
            category TEXT,
            organiser TEXT,
            ticketed INTEGER,
            price_min REAL,
            currency TEXT NOT NULL DEFAULT 'SGD',
            booking_url TEXT,
            source_url TEXT NOT NULL,
            source_id TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(entity_id) REFERENCES discovery_entities(id),
            FOREIGN KEY(source_id) REFERENCES discovery_sources(id)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS discovery_event_profiles_starts_at_idx
        ON discovery_event_profiles(starts_at)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS discovery_entities_active_location_idx
        ON discovery_entities(status, latitude, longitude)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS discovery_source_records_source_entity_idx
        ON discovery_source_records(source_id, entity_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS discovery_food_evidence_entity_expiry_idx
        ON discovery_food_evidence(entity_id, expires_at)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS discovery_food_evidence_dimension_idx
        ON discovery_food_evidence(dimension, evidence_type)
        """
    )
    # Retired integrations keep their audit trail but cannot surface publicly.
    cursor.execute(
        """
        UPDATE discovery_sources
        SET active = 0, updated_at = CURRENT_TIMESTAMP
        WHERE id IN ('eventbrite_api', 'today_do_what', 'ticketmaster_public')
        """
    )
    cursor.execute(
        """
        UPDATE discovery_entities
        SET status = 'archived', updated_at = CURRENT_TIMESTAMP
        WHERE status = 'active'
          AND id IN (
              SELECT entity_id FROM discovery_source_records
              WHERE source_id IN (
                  'eventbrite_api', 'today_do_what', 'ticketmaster_public'
              )
          )
        """
    )
