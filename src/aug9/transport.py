from aug9.models import Route, RouteResult, SearchStatus


def get_sg_route(
    origin: str,
    destination: str,
) -> RouteResult:
    return RouteResult(
        status=SearchStatus.SUCCESS,
        route=Route(
            origin=origin,
            destination=destination,
            steps=[
                "Route planning capability is being built."
            ],
        ),
    )
