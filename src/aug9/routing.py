from aug9.models import Route, RouteResult, SearchStatus
from aug9.osrm import get_walking_route


WALKING_METERS_PER_MINUTE = 80.0


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
    # The public OSRM demo can return motor-vehicle timing even when a walking
    # profile is requested. Derive a conservative walking estimate from the
    # returned route distance instead of presenting that timing as pedestrian.
    duration_minutes = round(distance_meters / WALKING_METERS_PER_MINUTE, 1)
    steps = []

    for step in route["legs"][0]["steps"]:
        step_name = step["name"]

        if step_name and (not steps or steps[-1] != step_name):
            steps.append(step_name)

    summary = (
        f"Walk from {origin_name} "
        f"to {destination_name} "
        f"in about {duration_minutes:g} minutes"
        + (f" via {', '.join(steps[:3])}." if steps else ".")
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
