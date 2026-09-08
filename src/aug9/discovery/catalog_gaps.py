from __future__ import annotations

import re
import sqlite3

import psycopg

from aug9.core import database


def normalize_catalog_query(query: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", query.casefold()))


def record_catalog_gap(entity_type: str, query: str) -> bool:
    """Record an anonymous missing-catalog query without risking the user response."""
    normalized = normalize_catalog_query(query)
    if not normalized:
        return False
    try:
        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        cursor.execute(
            f"""
            INSERT INTO discovery_catalog_gaps (
                entity_type, query, normalized_query, occurrences
            ) VALUES ({p}, {p}, {p}, 1)
            ON CONFLICT(entity_type, normalized_query) DO UPDATE SET
                query = excluded.query,
                occurrences = discovery_catalog_gaps.occurrences + 1,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            (entity_type, query.strip(), normalized),
        )
        conn.commit()
        conn.close()
        return True
    except (psycopg.Error, sqlite3.Error):
        return False
