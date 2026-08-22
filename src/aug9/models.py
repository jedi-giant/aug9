from pydantic import BaseModel


class Location(BaseModel):
    name: str
    address: str
    postal_code: str
    latitude: float
    longitude: float

from enum import Enum


class SearchStatus(str, Enum):
    SUCCESS = "success"
    NO_RESULTS = "no_results"
    NETWORK_ERROR = "network_error"
    API_ERROR = "api_error"

class LocationSearchResult(BaseModel):
    status: SearchStatus
    location: Location | None = None
    message: str | None = None

class Settings(BaseModel):
    onemap_email: str
    onemap_password: str
    onemap_base_url: str
