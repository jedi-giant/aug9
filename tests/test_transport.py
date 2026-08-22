from aug9.transport import get_sg_route
from aug9.models import SearchStatus


def test_get_sg_route_returns_route():
    result = get_sg_route(
        "Maxwell Food Centre",
        "Marina Bay Sands",
    )

    assert result.status == SearchStatus.SUCCESS
    assert result.route is not None
    assert result.route.origin == "Maxwell Food Centre"
    assert result.route.destination == "Marina Bay Sands"
