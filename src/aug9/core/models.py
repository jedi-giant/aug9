from pydantic import BaseModel


class Place(BaseModel):
    name: str
    place_type: str | None = None
    address: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
