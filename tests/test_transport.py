from unittest.mock import patch

from aug9.models import SearchStatus
from aug9.transport import get_sg_route


@patch("aug9.transport.calculate_route")
@patch("aug9.transport.search_location")
def test_get_sg_route_returns_route(
    mock_search_location,
    mock_calculate_route,
):
    from aug9.models import (
        Location,
        LocationSearchResult,
        Route,
        RouteResult,
    )

    mock_search_location.side_effect = [
        LocationSearchResult(
            status=SearchStatus.SUCCESS,
            location=Location(
                name="Maxwell Food Centre",
                address="1 Kadayanallur Street",
                postal_code="069184",
                latitude=1.280331,
                longitude=103.844747,
            ),
        ),
        LocationSearchResult(
            status=SearchStatus.SUCCESS,
            location=Location(
                name="Marina Bay Sands",
                address="10 Bayfront Avenue",
                postal_code="018956",
                latitude=1.2838,
                longitude=103.8591,
            ),
        ),
    ]

    mock_calculate_route.return_value = RouteResult(
        status=SearchStatus.SUCCESS,
        route=Route(
            origin="Maxwell Food Centre",
            destination="Marina Bay Sands",
            steps=["Bayfront Avenue"],
        ),
    )

    result = get_sg_route(
        "base_url",
        "token",
        "Maxwell Food Centre",
        "Marina Bay Sands",
    )

    assert result.status == SearchStatus.SUCCESS
    assert result.route is not None
    assert result.route.origin == "Maxwell Food Centre"
