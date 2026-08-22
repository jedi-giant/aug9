from aug9.models import (
    Route,
    RouteResult,
    SearchStatus,
)
from aug9.onemap import (
    get_token,
    search_location,
)
from aug9.routing import calculate_route


def get_sg_route(
    base_url: str,
    token: str,
    origin: str,
    destination: str,
) -> RouteResult:

    origin_result = search_location(
        base_url,
        token,
        origin,
    )

    if origin_result.status != SearchStatus.SUCCESS:
        return RouteResult(
            status=origin_result.status,
            message=origin_result.message,
        )

    destination_result = search_location(
        base_url,
        token,
        destination,
    )

    if destination_result.status != SearchStatus.SUCCESS:
        return RouteResult(
            status=destination_result.status,
            message=destination_result.message,
        )

    return calculate_route(
        origin_result.location.latitude,
        origin_result.location.longitude,
        destination_result.location.latitude,
        destination_result.location.longitude,
        origin,
        destination,
    )
