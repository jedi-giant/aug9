from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx

from aug9.core.models import Place
from aug9.models import Route, RouteResult, SearchStatus
from aug9.routing import calculate_route
from aug9.sg_place.provider import OneMapProvider


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


class OneMapRouteProvider:
    """Native Singapore multimodal routing with a bounded OSRM fallback."""

    def __init__(
        self,
        onemap: OneMapProvider,
        fallback: RouteProvider | None = None,
    ) -> None:
        self.onemap = onemap
        self.fallback = fallback

    def route(self, origin: Place, destination: Place) -> RouteResult:
        return self.route_for_mode(origin, destination, "walk")

    def route_for_mode(
        self,
        origin: Place,
        destination: Place,
        mode: str,
    ) -> RouteResult:
        if any(
            value is None
            for value in (
                origin.latitude,
                origin.longitude,
                destination.latitude,
                destination.longitude,
            )
        ):
            raise ValueError("Origin and destination coordinates are required")
        route_type = {
            "walk": "walk",
            "public_transport": "pt",
            "drive": "drive",
            "taxi_or_drive": "drive",
            "cycle": "cycle",
        }.get(mode, "walk")
        token = self.onemap.authenticate()
        if token is None or not self.onemap.base_url:
            return self._fallback(
                origin, destination, mode, "OneMap authentication failed"
            )

        params = {
            "start": f"{origin.latitude},{origin.longitude}",
            "end": f"{destination.latitude},{destination.longitude}",
            "routeType": route_type,
        }
        if route_type == "pt":
            now = datetime.now(ZoneInfo("Asia/Singapore"))
            params.update(
                {
                    "date": now.strftime("%m-%d-%Y"),
                    "time": now.strftime("%H:%M:%S"),
                    "mode": "TRANSIT",
                    "maxWalkDistance": "1000",
                    "numItineraries": "1",
                }
            )
        try:
            response = httpx.get(
                f"{self.onemap.base_url}/api/public/routingsvc/route",
                params=params,
                headers={"Authorization": token},
                timeout=self.onemap.timeout,
            )
            response.raise_for_status()
            return self._parse(response.json(), origin, destination, mode)
        except (httpx.RequestError, httpx.HTTPStatusError, KeyError, ValueError) as exc:
            return self._fallback(origin, destination, mode, type(exc).__name__)

    def _fallback(
        self, origin: Place, destination: Place, mode: str, message: str
    ) -> RouteResult:
        if self.fallback is not None and mode == "walk":
            return self.fallback.route(origin, destination)
        return RouteResult(status=SearchStatus.API_ERROR, message=message)

    @staticmethod
    def _parse(data, origin: Place, destination: Place, mode: str) -> RouteResult:
        if "route_summary" in data:
            route_summary = data["route_summary"]
            steps = [
                str(item[-1])
                for item in data.get("route_instructions", [])
                if isinstance(item, list) and item and item[-1]
            ]
            distance = float(route_summary["total_distance"])
            duration = round(float(route_summary["total_time"]) / 60, 1)
        else:
            itinerary = data["plan"]["itineraries"][0]
            legs = itinerary.get("legs", [])
            steps = []
            for leg in legs:
                from_name = (leg.get("from") or {}).get("name")
                to_name = (leg.get("to") or {}).get("name")
                leg_mode = str(leg.get("mode", "transit")).replace("_", " ").title()
                if from_name and to_name:
                    steps.append(f"{leg_mode}: {from_name} to {to_name}")
            distance = float(
                itinerary.get("walkDistance")
                or sum(float(leg.get("distance", 0)) for leg in legs)
            )
            duration = round(float(itinerary["duration"]) / 60, 1)
        label = {
            "walk": "Walk",
            "public_transport": "Take public transport",
            "drive": "Drive",
            "taxi_or_drive": "Take a taxi or drive",
            "cycle": "Cycle",
        }.get(mode, "Travel")
        return RouteResult(
            status=SearchStatus.SUCCESS,
            route=Route(
                origin=origin.name,
                destination=destination.name,
                steps=steps,
                summary=(
                    f"{label} from {origin.name} to {destination.name} "
                    f"in about {duration:g} minutes."
                ),
                distance_meters=distance,
                duration_minutes=duration,
            ),
        )
