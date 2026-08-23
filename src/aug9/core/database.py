import sqlite3
from pathlib import Path

from aug9.core.embeddings import create_embedding


DB_PATH = Path("aug9.db")


def get_connection():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=10,
    )

    return conn


def initialise_database():

    conn = get_connection()

    cursor = conn.cursor()

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

    # Prevent duplicate memories
    cursor.execute(
        """
        SELECT id
        FROM memories
        WHERE user_id = ?
        AND category = ?
        AND value = ?
        AND memory_type = ?
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


    # Save memory
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


    # Commit memory first
    # This releases SQLite lock
    conn.commit()
    conn.close()


    # Generate embedding after transaction completes
    embedding = create_embedding(
        value
    )


    # Save embedding separately
    save_embedding(
        memory_id,
        embedding,
    )


def get_memories(
    user_id: str,
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            category,
            value,
            memory_type,
            confidence,
            expires
        FROM memories
        WHERE user_id = ?
        """,
        (
            user_id,
        ),
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

    cursor.execute(
        """
        INSERT INTO memory_embeddings (
            memory_id,
            embedding
        )
        VALUES (?, ?)
        """,
        (
            memory_id,
            str(embedding),
        ),
    )

    conn.commit()
    conn.close()



def get_embeddings():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            memory_id,
            embedding
        FROM memory_embeddings
        """
    )

    rows = cursor.fetchall()

    conn.close()

    return rows
