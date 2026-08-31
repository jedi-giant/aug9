def initialise_product_analytics_schema(cursor, *, postgres: bool) -> None:
    id_column = "BIGSERIAL PRIMARY KEY" if postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS product_events (
            id {id_column},
            event_id TEXT NOT NULL UNIQUE,
            task_id TEXT,
            user_id TEXT NOT NULL,
            session_id TEXT,
            event_type TEXT NOT NULL,
            capabilities TEXT NOT NULL DEFAULT '[]',
            task_status TEXT,
            action_type TEXT,
            helpful INTEGER,
            successful_task INTEGER NOT NULL DEFAULT 0,
            campaign_source TEXT,
            campaign_medium TEXT,
            campaign_name TEXT,
            ranking_mode TEXT,
            feedback_scope TEXT,
            target_id TEXT,
            journey_type TEXT,
            journey_status TEXT,
            failure_stage TEXT,
            reason_code TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    if postgres:
        cursor.execute(
            "ALTER TABLE product_events ADD COLUMN IF NOT EXISTS ranking_mode TEXT"
        )
        cursor.execute(
            "ALTER TABLE product_events ADD COLUMN IF NOT EXISTS feedback_scope TEXT"
        )
        cursor.execute(
            "ALTER TABLE product_events ADD COLUMN IF NOT EXISTS target_id TEXT"
        )
        cursor.execute(
            "ALTER TABLE product_events ADD COLUMN IF NOT EXISTS reason_code TEXT"
        )
        cursor.execute(
            "ALTER TABLE product_events ADD COLUMN IF NOT EXISTS journey_type TEXT"
        )
        cursor.execute(
            "ALTER TABLE product_events ADD COLUMN IF NOT EXISTS journey_status TEXT"
        )
        cursor.execute(
            "ALTER TABLE product_events ADD COLUMN IF NOT EXISTS failure_stage TEXT"
        )
    else:
        cursor.execute("PRAGMA table_info(product_events)")
        columns = {row[1] for row in cursor.fetchall()}
        for column in (
            "ranking_mode",
            "feedback_scope",
            "target_id",
            "reason_code",
            "journey_type",
            "journey_status",
            "failure_stage",
        ):
            if column not in columns:
                cursor.execute(
                    f"ALTER TABLE product_events ADD COLUMN {column} TEXT"
                )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS product_events_task_id_idx
        ON product_events(task_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS product_events_created_at_idx
        ON product_events(created_at)
        """
    )
