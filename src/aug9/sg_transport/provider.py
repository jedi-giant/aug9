from typing import Protocol

import httpx

from aug9.core.models import Place
from aug9.models import RouteResult, SearchStatus
from aug9.routing import calculate_route


class RouteProvider(Protocol):
    def route(self, origin: Place, destination: Place) -> RouteResult: ...


class OsrmRouteProvider:
    """Walking-route adapter backed by the existing OSRM integration."""

    def route(self, origin: Place, destination: Place) -> RouteResult:
        if (
            origin.latitude is None
            or origin.longitude is None
            or destination.latitude is None
            or destination.longitude is None
        ):
            raise ValueError("Origin and destination coordinates are required")

        try:
            return calculate_route(
                origin.latitude,
                origin.longitude,
                destination.latitude,
                destination.longitude,
                origin.name,
                destination.name,
            )
        except httpx.RequestError as exc:
            return RouteResult(
                status=SearchStatus.NETWORK_ERROR,
                message=str(exc),
            )
        except httpx.HTTPStatusError as exc:
            return RouteResult(
                status=SearchStatus.API_ERROR,
                message=f"HTTP {exc.response.status_code}",
            )
