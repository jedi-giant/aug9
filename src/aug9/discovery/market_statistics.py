from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel

from aug9.core import database
from aug9.discovery.models import DiscoverySource, SourcePermission
from aug9.discovery.repository import DiscoveryRepository


FOOD_ESTABLISHMENTS_SOURCE_ID = "nea_food_establishment_statistics"
FOOD_ESTABLISHMENTS_DATASETS = (
    "d_dbf37846568f6a5595b4f16f110b4619",
    "d_6188a67536a7a12751ee690e96b506fa",
)
DATASTORE_URL = "https://data.gov.sg/api/action/datastore_search"


class MarketStatistic(BaseModel):
    source_id: str
    dataset_id: str
    external_id: str
    metric: str
    category: str | None = None
    period: str
    value: float
    unit: str
    geography: str = "Singapore"
    raw_payload: dict[str, Any]
    fetched_at: datetime


@dataclass(frozen=True)
class MarketStatisticsImportSummary:
    run_id: str
    received: int
    upserted: int
    rejected: int


class MarketStatisticsRepository:
    def upsert(self, statistic: MarketStatistic) -> None:
        self.upsert_many([statistic])

    def upsert_many(self, statistics: list[MarketStatistic]) -> None:
        if not statistics:
            return
        source_ids = {statistic.source_id for statistic in statistics}
        if len(source_ids) != 1:
            raise ValueError("Market statistics batch must use one source")

        conn = database.get_connection()
        cursor = conn.cursor()
        p = database.placeholder()
        try:
            cursor.execute(
                f"SELECT permission FROM discovery_sources WHERE id = {p}",
                (statistics[0].source_id,),
            )
            row = cursor.fetchone()
            ingestable = {
                SourcePermission.OPEN_DATA.value,
                SourcePermission.LICENSED_PARTNER.value,
            }
            if row is None or row[0] not in ingestable:
                raise ValueError("Market statistic source does not allow ingestion")
            for statistic in statistics:
                cursor.execute(
                    f"""
                    INSERT INTO market_statistics (
                        source_id, dataset_id, external_id, metric, category,
                        period, value, unit, geography, raw_payload, fetched_at
                    ) VALUES (
                        {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}
                    )
                    ON CONFLICT(source_id, dataset_id, external_id) DO UPDATE SET
                        metric = excluded.metric,
                        category = excluded.category,
                        period = excluded.period,
                        value = excluded.value,
                        unit = excluded.unit,
                        geography = excluded.geography,
                        raw_payload = excluded.raw_payload,
                        fetched_at = excluded.fetched_at,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        statistic.source_id,
                        statistic.dataset_id,
                        statistic.external_id,
                        statistic.metric,
                        statistic.category,
                        statistic.period,
                        statistic.value,
                        statistic.unit,
                        statistic.geography,
                        json.dumps(statistic.raw_payload, sort_keys=True),
                        statistic.fetched_at.isoformat(),
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


class FoodEstablishmentStatisticsImporter:
    def __init__(
        self,
        discovery_repository: DiscoveryRepository,
        statistics_repository: MarketStatisticsRepository | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.discovery_repository = discovery_repository
        self.statistics_repository = (
            statistics_repository or MarketStatisticsRepository()
        )
        headers = {}
        if api_key := os.getenv("DATA_GOV_SG_API_KEY"):
            headers["x-api-key"] = api_key
        self.client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers=headers,
        )

    def run(self) -> MarketStatisticsImportSummary:
        self.discovery_repository.register_source(
            DiscoverySource(
                id=FOOD_ESTABLISHMENTS_SOURCE_ID,
                name="Licensed Food Establishments by Category, Annual",
                permission=SourcePermission.OPEN_DATA,
                base_url="https://data.gov.sg/collections/1447/view",
                license_name="Singapore Open Data Licence 1.0",
                attribution=(
                    "Singapore Food Agency and National Environment Agency "
                    "via data.gov.sg"
                ),
            )
        )
        run = self.discovery_repository.start_ingestion(
            FOOD_ESTABLISHMENTS_SOURCE_ID
        )
        received = upserted = rejected = 0
        try:
            fetched_at = datetime.now(UTC)
            statistics: list[MarketStatistic] = []
            for dataset_id in FOOD_ESTABLISHMENTS_DATASETS:
                for row in self.fetch_rows(dataset_id):
                    received += 1
                    try:
                        statistics.append(
                            self.normalise(dataset_id, row, fetched_at)
                        )
                    except (KeyError, TypeError, ValueError):
                        rejected += 1
            self.statistics_repository.upsert_many(statistics)
            upserted = len(statistics)
            self.discovery_repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=upserted,
                records_rejected=rejected,
            )
            return MarketStatisticsImportSummary(
                run.id, received, upserted, rejected
            )
        except Exception as exc:
            self.discovery_repository.complete_ingestion(
                run,
                records_received=received,
                records_upserted=upserted,
                records_rejected=rejected,
                error=type(exc).__name__,
            )
            raise

    def fetch_rows(self, dataset_id: str) -> list[dict[str, Any]]:
        response = self.client.get(
            DATASTORE_URL,
            params={"resource_id": dataset_id, "limit": 1000},
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result")
        rows = result.get("records") if isinstance(result, dict) else None
        if payload.get("success") is not True or not isinstance(rows, list):
            raise ValueError("data.gov.sg response does not contain records")
        total = result.get("total")
        if isinstance(total, int) and total > len(rows):
            raise ValueError("data.gov.sg dataset exceeds the bulk import limit")
        return rows

    @staticmethod
    def normalise(
        dataset_id: str,
        row: dict[str, Any],
        fetched_at: datetime,
    ) -> MarketStatistic:
        year = str(row["year"]).strip()
        if len(year) != 4 or not year.isdigit():
            raise ValueError("Invalid statistics year")
        value = float(row["value"])
        if value < 0:
            raise ValueError("Statistic value cannot be negative")
        external_id = str(row.get("vault_id") or row.get("_id") or "").strip()
        if not external_id:
            raise ValueError("Statistic is missing its source row id")
        category = str(row.get("level_2") or "").strip() or None
        metric = str(row.get("level_1") or "").strip()
        if not metric:
            raise ValueError("Statistic is missing its metric")
        return MarketStatistic(
            source_id=FOOD_ESTABLISHMENTS_SOURCE_ID,
            dataset_id=dataset_id,
            external_id=external_id,
            metric=metric,
            category=category,
            period=year,
            value=value,
            unit="establishments",
            raw_payload=row,
            fetched_at=fetched_at,
        )
