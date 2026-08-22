import httpx


OSRM_URL = (
    "https://router.project-osrm.org/"
    "route/v1/walking/"
)


def get_walking_route(
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
) -> dict:

    url = (
        f"{OSRM_URL}"
        f"{origin_longitude},{origin_latitude};"
        f"{destination_longitude},{destination_latitude}"
    )

    response = httpx.get(
        url,
        params={
            "steps": "true",
            "overview": "false",
        },
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()
