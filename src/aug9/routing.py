from aug9.models import Route, RouteResult, SearchStatus
from aug9.osrm import get_walking_route


def calculate_route(
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
    origin_name: str,
    destination_name: str,
) -> RouteResult:

    data = get_walking_route(
        origin_latitude,
        origin_longitude,
        destination_latitude,
        destination_longitude,
    )

    route = data["routes"][0]
    distance_meters = route["distance"]
    duration_minutes = route["duration"] / 60
    steps = []

    for step in route["legs"][0]["steps"]:
        step_name = step["name"]

        if step_name:
            steps.append(step_name)

    summary = (
        f"Walk from {origin_name} "
        f"to {destination_name} "
        f"via {', '.join(steps[:3])}."
    )

    return RouteResult(
        status=SearchStatus.SUCCESS,
        route=Route(
            origin=origin_name,
            destination=destination_name,
            steps=steps,
            summary=summary,
            distance_meters=distance_meters,
            duration_minutes=duration_minutes,
        ),
    )
