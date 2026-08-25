import math
from typing import Protocol

import httpx

from aug9.core.models import Place
from aug9.models import SearchStatus, Weather, WeatherResult

WEATHER_URL = "https://api-open.data.gov.sg/v2/real-time/api/two-hr-forecast"


class WeatherProvider(Protocol):
    def forecast(self, place: Place) -> WeatherResult: ...


def distance_between(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    return math.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2)


class DataGovSgWeatherProvider:
    """Adapter for data.gov.sg's two-hour area forecast."""

    def __init__(self, url: str = WEATHER_URL, *, timeout: float = 10.0) -> None:
        self.url = url
        self.timeout = timeout

    def forecast(self, place: Place) -> WeatherResult:
        if place.latitude is None or place.longitude is None:
            return WeatherResult(
                status=SearchStatus.NO_RESULTS,
                message="Location coordinates are unavailable.",
            )

        try:
            response = httpx.get(self.url, timeout=self.timeout)
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
                place.latitude,
                place.longitude,
                area["label_location"]["latitude"],
                area["label_location"]["longitude"],
            ),
        )
        forecast_text = next(
            item["forecast"]
            for item in forecasts
            if item["area"] == nearest_area["name"]
        )

        return WeatherResult(
            status=SearchStatus.SUCCESS,
            weather=Weather(forecast=forecast_text),
        )
