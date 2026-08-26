import httpx

from aug9.sg_services.catalog_report import build_service_catalog_report
from aug9.sg_services.provider import GovernmentService


SERVICES = (
    GovernmentService(
        name="Working service",
        agency="Agency A",
        description="Official service.",
        url="https://agency-a.gov.sg/service",
        topics=("working",),
    ),
    GovernmentService(
        name="Broken service",
        agency="Agency B",
        description="Official service.",
        url="https://agency-b.gov.sg/service",
        topics=("broken",),
    ),
    GovernmentService(
        name="Bot-blocked service",
        agency="Agency C",
        description="Official service.",
        url="https://agency-c.gov.sg/service",
        topics=("blocked",),
    ),
)


class FakeClient:
    def get(self, url: str) -> httpx.Response:
        request = httpx.Request("GET", url)
        if "agency-a" in url:
            return httpx.Response(
                200,
                request=request,
                headers={"location": "https://agency-a.gov.sg/service"},
            )
        if "agency-c" in url:
            return httpx.Response(403, request=request)
        raise httpx.ConnectTimeout("timed out", request=request)


def test_service_catalog_report_counts_health_and_contains_no_page_content():
    report = build_service_catalog_report(services=SERVICES, client=FakeClient())

    assert report.total_services == 3
    assert report.healthy_links == 1
    assert report.unhealthy_links == 1
    assert report.blocked_checks == 1
    assert report.services[0].status_code == 200
    assert report.services[1].error == "ConnectTimeout"
    assert report.services[1].status_code is None
    assert report.services[2].verification_status == "blocked"
