from datetime import UTC, datetime
from typing import Protocol

import httpx
from pydantic import BaseModel

from aug9.sg_services.provider import OFFICIAL_SERVICES, GovernmentService


class HttpClient(Protocol):
    def get(self, url: str) -> httpx.Response: ...


class ServiceLinkStatus(BaseModel):
    name: str
    agency: str
    url: str
    healthy: bool
    verification_status: str
    status_code: int | None = None
    final_url: str | None = None
    error: str | None = None


class ServiceCatalogReport(BaseModel):
    generated_at: datetime
    total_services: int
    healthy_links: int
    unhealthy_links: int
    blocked_checks: int
    services: list[ServiceLinkStatus]


def build_service_catalog_report(
    *,
    services: tuple[GovernmentService, ...] = OFFICIAL_SERVICES,
    client: HttpClient | None = None,
) -> ServiceCatalogReport:
    owns_client = client is None
    if client is None:
        client = httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={"User-Agent": "Aug9-Service-Link-Health/1.0"},
        )
    results: list[ServiceLinkStatus] = []
    try:
        for service in services:
            try:
                response = client.get(str(service.url))
                results.append(
                    ServiceLinkStatus(
                        name=service.name,
                        agency=service.agency,
                        url=str(service.url),
                        healthy=200 <= response.status_code < 400,
                        verification_status=(
                            "healthy"
                            if 200 <= response.status_code < 400
                            else "blocked"
                            if response.status_code in {401, 403, 429}
                            else "unhealthy"
                        ),
                        status_code=response.status_code,
                        final_url=str(response.url),
                    )
                )
            except httpx.HTTPError as exc:
                results.append(
                    ServiceLinkStatus(
                        name=service.name,
                        agency=service.agency,
                        url=str(service.url),
                        healthy=False,
                        verification_status="unhealthy",
                        error=type(exc).__name__,
                    )
                )
    finally:
        if owns_client:
            client.close()  # type: ignore[attr-defined]
    healthy = sum(result.healthy for result in results)
    blocked = sum(result.verification_status == "blocked" for result in results)
    return ServiceCatalogReport(
        generated_at=datetime.now(UTC),
        total_services=len(results),
        healthy_links=healthy,
        unhealthy_links=len(results) - healthy - blocked,
        blocked_checks=blocked,
        services=results,
    )
