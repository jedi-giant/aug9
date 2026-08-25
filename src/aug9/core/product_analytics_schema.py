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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
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
