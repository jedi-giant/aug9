from enum import Enum

from pydantic import BaseModel
from aug9.core.models import Place

class FoodRecommendation(BaseModel):
    name: str
    description: str
    place: Place

class SearchStatus(str, Enum):
    SUCCESS = "success"
    NO_RESULTS = "no_results"
    NETWORK_ERROR = "network_error"
    API_ERROR = "api_error"

class PlaceSearchResult(BaseModel):
    status: SearchStatus
    location: Place | None = None
    message: str | None = None

class Weather(BaseModel):
    temperature_c: float | None = None
    forecast: str | None = None
    rainfall_mm: float | None = None


class WeatherResult(BaseModel):
    status: SearchStatus
    weather: Weather | None = None
    message: str | None = None


class Settings(BaseModel):
    onemap_email: str
    onemap_password: str
    onemap_base_url: str

class Route(BaseModel):
    origin: str
    destination: str
    steps: list[str]
    summary: str | None = None
    distance_meters: float | None = None
    duration_minutes: float | None = None

class RouteResult(BaseModel):
    status: SearchStatus
    route: Route | None = None
    message: str | None = None

class FoodResult(BaseModel):
    status: SearchStatus
    recommendations: list[FoodRecommendation]
    message: str | None = None
