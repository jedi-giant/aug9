import json

import httpx
import pytest

from aug9.core import database
from aug9.discovery.market_statistics import (
    DATASET_API_ROOT,
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
            "vault_id": "1", "year": "1993",
            "level_1": "Total Licensed Food Establishments", "value": "20642",
        }],
        second_dataset: [{
            "vault_id": "1", "year": "1993",
            "level_1": "Total Licensed Food Establishments",
            "level_2": "Food Shops", "value": "7469",
        }],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        dataset_id = request.url.path.split("/")[-2]
        return httpx.Response(200, json={
            "code": 0,
            "data": {"rows": responses[dataset_id], "links": {}},
            "errorMsg": "",
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


def test_food_statistics_importer_follows_pagination(repository):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        cursor = request.url.params.get("idCursor[value]")
        if cursor is None:
            rows = [{
                "vault_id": "1", "year": "2016",
                "level_1": "Total Licensed Food Establishments", "value": "1",
            }]
            links = {"next": "idCursor%5Bvalue%5D=1"}
        else:
            rows = [{
                "vault_id": "2", "year": "2017",
                "level_1": "Total Licensed Food Establishments", "value": "2",
            }]
            links = {}
        return httpx.Response(
            200, json={"code": 0, "data": {"rows": rows, "links": links}}
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    importer = FoodEstablishmentStatisticsImporter(repository, client=client)
    rows = importer.fetch_rows(FOOD_ESTABLISHMENTS_DATASETS[0])

    assert len(rows) == 2
    assert len(calls) == 2
    assert calls[0].startswith(DATASET_API_ROOT)


def test_food_statistics_importer_rejects_bad_rows(repository):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "code": 0,
            "data": {
                "rows": [{
                    "vault_id": "bad", "year": "unknown",
                    "level_1": "Total Licensed Food Establishments",
                    "value": "not-a-number",
                }],
                "links": {},
            },
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    summary = FoodEstablishmentStatisticsImporter(repository, client=client).run()

    assert summary.received == 2
    assert summary.upserted == 0
    assert summary.rejected == 2
