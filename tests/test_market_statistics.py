import json

import httpx
import pytest

from aug9.core import database
from aug9.discovery.market_statistics import (
    DATASTORE_URL,
    FOOD_ESTABLISHMENTS_DATASETS,
    FoodEstablishmentStatisticsImporter,
)
from aug9.discovery.repository import DiscoveryRepository


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(database, "SQLITE_DB_PATH", tmp_path / "statistics.db")
    database.initialise_database()
    return DiscoveryRepository()


def test_food_statistics_importer_keeps_aggregates_out_of_discovery(repository):
    first_dataset, second_dataset = FOOD_ESTABLISHMENTS_DATASETS
    responses = {
        first_dataset: [{
            "_id": 1, "year": "1993",
            "level_1": "Total Licensed Food Establishments", "value": "20642",
        }],
        second_dataset: [{
            "_id": 1, "year": "1993",
            "level_1": "Total Licensed Food Establishments",
            "level_2": "Food Shops", "value": "7469",
        }],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        dataset_id = request.url.params["resource_id"]
        return httpx.Response(200, json={
            "success": True,
            "result": {
                "records": responses[dataset_id],
                "total": len(responses[dataset_id]),
            },
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    summary = FoodEstablishmentStatisticsImporter(repository, client=client).run()

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT dataset_id, metric, category, period, value, unit, raw_payload
        FROM market_statistics ORDER BY dataset_id
        """
    )
    rows = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) FROM discovery_entities")
    entity_count = cursor.fetchone()[0]
    conn.close()

    assert summary.received == 2
    assert summary.upserted == 2
    assert summary.rejected == 0
    assert entity_count == 0
    assert {row[2] for row in rows} == {None, "Food Shops"}
    assert {row[3] for row in rows} == {"1993"}
    assert {row[4] for row in rows} == {20642.0, 7469.0}
    assert {row[5] for row in rows} == {"establishments"}
    assert json.loads(rows[0][6])["year"] == "1993"


def test_food_statistics_importer_uses_single_bulk_request(repository):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        rows = [
            {"vault_id": "1", "year": "2016",
             "level_1": "Total Licensed Food Establishments", "value": "1"},
            {"vault_id": "2", "year": "2017",
             "level_1": "Total Licensed Food Establishments", "value": "2"},
        ]
        return httpx.Response(200, json={
            "success": True,
            "result": {"records": rows, "total": 2},
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    importer = FoodEstablishmentStatisticsImporter(repository, client=client)
    rows = importer.fetch_rows(FOOD_ESTABLISHMENTS_DATASETS[0])

    assert len(rows) == 2
    assert len(calls) == 1
    assert calls[0].startswith(DATASTORE_URL)
    assert "limit=1000" in calls[0]


def test_food_statistics_importer_rejects_bad_rows(repository):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "success": True,
            "result": {
                "records": [{
                    "vault_id": "bad", "year": "unknown",
                    "level_1": "Total Licensed Food Establishments",
                    "value": "not-a-number",
                }],
                "total": 1,
            },
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    summary = FoodEstablishmentStatisticsImporter(repository, client=client).run()

    assert summary.received == 2
    assert summary.upserted == 0
    assert summary.rejected == 2
