import os
import sqlite3
from pathlib import Path

import psycopg

from aug9.discovery.schema import initialise_discovery_schema
from aug9.core.product_analytics_schema import initialise_product_analytics_schema


SQLITE_DB_PATH = Path(
    os.getenv(
        "AUG9_DB_PATH",
        "aug9.db",
    )
)


def _positive_int_environment(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def is_postgres() -> bool:
    database_url = os.getenv(
        "DATABASE_URL"
    )

    return bool(
        database_url
        and database_url.startswith(
            (
                "postgres://",
                "postgresql://",
            )
        )
    )


def get_connection():
    """
    Use PostgreSQL when DATABASE_URL is available.
    Otherwise fall back to local SQLite.
    """

    if is_postgres():
        connect_timeout = _positive_int_environment(
            "DATABASE_CONNECT_TIMEOUT_SECONDS", 10
        )
        statement_timeout_ms = 1000 * _positive_int_environment(
            "DATABASE_STATEMENT_TIMEOUT_SECONDS", 60
        )
        lock_timeout_ms = 1000 * _positive_int_environment(
            "DATABASE_LOCK_TIMEOUT_SECONDS", 10
        )
        return psycopg.connect(
            os.environ["DATABASE_URL"],
            connect_timeout=connect_timeout,
            application_name="aug9",
            options=(
                f"-c statement_timeout={statement_timeout_ms} "
                f"-c lock_timeout={lock_timeout_ms}"
            ),
        )

    return sqlite3.connect(
        SQLITE_DB_PATH,
        timeout=10,
    )


def placeholder() -> str:
    """
    SQLite uses ?
    PostgreSQL/psycopg uses %s
    """

    if is_postgres():
        return "%s"

    return "?"


def initialise_database():
    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                category TEXT NOT NULL,
                value TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                expires INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_embeddings (
                id BIGSERIAL PRIMARY KEY,
                memory_id BIGINT NOT NULL,
                embedding TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(memory_id)
                    REFERENCES memories(id)
                    ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_events (
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_id TEXT,
                message_length INTEGER NOT NULL,
                status TEXT NOT NULL,
                latency_ms INTEGER,
                error_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    else:

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                category TEXT NOT NULL,
                value TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                expires INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER NOT NULL,
                embedding TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(memory_id)
                    REFERENCES memories(id)
                    ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT,
                message_length INTEGER NOT NULL,
                status TEXT NOT NULL,
                latency_ms INTEGER,
                error_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    initialise_discovery_schema(
        cursor,
        postgres=is_postgres(),
    )
    initialise_product_analytics_schema(
        cursor,
        postgres=is_postgres(),
    )

    conn.commit()
    conn.close()


def save_memory(
    user_id: str,
    category: str,
    value: str,
    memory_type: str,
    confidence: float,
    expires: bool,
):
    conn = get_connection()
    cursor = conn.cursor()

    p = placeholder()

    cursor.execute(
        f"""
        SELECT id
        FROM memories
        WHERE user_id = {p}
          AND category = {p}
          AND value = {p}
          AND memory_type = {p}
        """,
        (
            user_id,
            category,
            value,
            memory_type,
        ),
    )

    existing = cursor.fetchone()

    if existing:
        conn.close()
        return

    if is_postgres():

        cursor.execute(
            """
            INSERT INTO memories (
                user_id,
                category,
                value,
                memory_type,
                confidence,
                expires
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                user_id,
                category,
                value,
                memory_type,
                confidence,
                int(expires),
            ),
        )

        memory_id = cursor.fetchone()[0]

    else:

        cursor.execute(
            """
            INSERT INTO memories (
                user_id,
                category,
                value,
                memory_type,
                confidence,
                expires
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                category,
                value,
                memory_type,
                confidence,
                int(expires),
            ),
        )

        memory_id = cursor.lastrowid

    conn.commit()
    conn.close()

    # Create embedding only after the memory transaction
    # has been committed and closed.
    from aug9.core.embeddings import create_embedding

    embedding = create_embedding(
        value
    )

    save_embedding(
        memory_id,
        embedding,
    )


def get_memories(
    user_id: str,
):
    conn = get_connection()
    cursor = conn.cursor()

    p = placeholder()

    cursor.execute(
        f"""
        SELECT
            category,
            value,
            memory_type,
            confidence,
            expires
        FROM memories
        WHERE user_id = {p}
        ORDER BY id ASC
        """,
        (user_id,),
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


def save_embedding(
    memory_id: int,
    embedding: list[float],
):
    conn = get_connection()
    cursor = conn.cursor()

    p = placeholder()

    cursor.execute(
        f"""
        INSERT INTO memory_embeddings (
            memory_id,
            embedding
        )
        VALUES ({p}, {p})
        """,
        (
            memory_id,
            str(embedding),
        ),
    )

    conn.commit()
    conn.close()


def get_embeddings(
    user_id: str,
):
    conn = get_connection()
    cursor = conn.cursor()

    p = placeholder()

    cursor.execute(
        f"""
        SELECT
            m.id,
            m.category,
            m.value,
            m.memory_type,
            m.confidence,
            m.expires,
            e.embedding
        FROM memories m
        JOIN memory_embeddings e
          ON e.memory_id = m.id
        WHERE m.user_id = {p}
        ORDER BY m.id ASC
        """,
        (user_id,),
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


def log_usage_event(
    user_id: str,
    session_id: str | None,
    message_length: int,
    status: str,
    latency_ms: int | None = None,
    error_type: str | None = None,
) -> None:
    conn = get_connection()
    cursor = conn.cursor()

    p = placeholder()

    cursor.execute(
        f"""
        INSERT INTO usage_events (
            user_id,
            session_id,
            message_length,
            status,
            latency_ms,
            error_type
        )
        VALUES (
            {p},
            {p},
            {p},
            {p},
            {p},
            {p}
        )
        """,
        (
            user_id,
            session_id,
            message_length,
            status,
            latency_ms,
            error_type,
        ),
    )

    conn.commit()
    conn.close()
