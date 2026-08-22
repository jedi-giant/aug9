import math

import httpx

from aug9.models import Location, Weather, WeatherResult, SearchStatus


WEATHER_URL = (
    "https://api-open.data.gov.sg/"
    "v2/real-time/api/two-hr-forecast"
)


def distance_between(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    return math.sqrt(
        (lat1 - lat2) ** 2
        + (lon1 - lon2) ** 2
    )


def get_weather(location: Location) -> WeatherResult:
    try:
        response = httpx.get(
            WEATHER_URL,
            timeout=10.0,
        )

        response.raise_for_status()

    except httpx.RequestError as exc:
        return WeatherResult(
            status=SearchStatus.NETWORK_ERROR,
            message=str(exc),
        )

    except httpx.HTTPStatusError as exc:
        return WeatherResult(
            status=SearchStatus.API_ERROR,
            message=f"HTTP {exc.response.status_code}",
        )

    data = response.json()["data"]

    areas = data["area_metadata"]
    forecasts = data["items"][0]["forecasts"]

    nearest_area = min(
        areas,
        key=lambda area: distance_between(
            location.latitude,
            location.longitude,
            area["label_location"]["latitude"],
            area["label_location"]["longitude"],
        ),
    )

    area_name = nearest_area["name"]

    forecast_text = next(
        item["forecast"]
        for item in forecasts
        if item["area"] == area_name
    )

    return WeatherResult(
        status=SearchStatus.SUCCESS,
        weather=Weather(
            forecast=forecast_text,
        ),
    )
