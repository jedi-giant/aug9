from __future__ import annotations

import os
from typing import Protocol

import httpx

from aug9.core.models import Place
from aug9.models import LocationSearchResult, SearchStatus


class PlaceProvider(Protocol):
    def search(self, query: str) -> LocationSearchResult: ...

    def reverse_geocode(self, latitude: float, longitude: float) -> LocationSearchResult: ...


class OneMapProvider:
    """OneMap adapter; authentication and HTTP details stay behind this boundary."""

    def __init__(
        self,
        base_url: str | None,
        email: str | None,
        password: str | None,
        *,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url
        self.email = email
        self.password = password
        self.timeout = timeout

    @classmethod
    def from_environment(cls) -> OneMapProvider:
        return cls(
            os.getenv("ONEMAP_BASE_URL"),
            os.getenv("ONEMAP_EMAIL"),
            os.getenv("ONEMAP_PASSWORD"),
        )

    def authenticate(self) -> str | None:
        if not self.base_url or not self.email or not self.password:
            return None

        try:
            response = httpx.post(
                f"{self.base_url}/api/auth/post/getToken",
                json={"email": self.email, "password": self.password},
                timeout=self.timeout,
            )
            response.raise_for_status()
            token = response.json().get("access_token")
        except (
            httpx.RequestError,
            httpx.HTTPStatusError,
            AttributeError,
            TypeError,
            ValueError,
        ):
            return None

        return token

    def search(self, query: str) -> LocationSearchResult:
        token = self.authenticate()
        if token is None:
            return LocationSearchResult(
                status=SearchStatus.API_ERROR,
                message="Unable to authenticate with OneMap.",
            )
        return self.search_with_token(query, token)

    def search_with_token(self, query: str, token: str) -> LocationSearchResult:
        if not self.base_url:
            return LocationSearchResult(
                status=SearchStatus.API_ERROR,
                message="OneMap base URL is not configured.",
            )

        try:
            response = httpx.get(
                f"{self.base_url}/api/common/elastic/search",
                params={
                    "searchVal": query,
                    "returnGeom": "Y",
                    "getAddrDetails": "Y",
                    "pageNum": 1,
                },
                headers={"Authorization": token},
                timeout=self.timeout,
            )
            response.raise_for_status()
            results = response.json().get("results", [])
        except httpx.RequestError as exc:
            return LocationSearchResult(
                status=SearchStatus.NETWORK_ERROR,
                message=str(exc),
            )
        except httpx.HTTPStatusError as exc:
            return LocationSearchResult(
                status=SearchStatus.API_ERROR,
                message=f"HTTP {exc.response.status_code}",
            )
        except (AttributeError, TypeError, ValueError):
            return LocationSearchResult(
                status=SearchStatus.API_ERROR,
                message="Invalid OneMap response.",
            )

        if not results:
            simplified = query.replace(", Singapore", "").replace(" Singapore", "").strip()
            if simplified != query:
                return self.search_with_token(simplified, token)
            return LocationSearchResult(
                status=SearchStatus.NO_RESULTS,
                message=f'No location found for "{query}".',
            )

        try:
            first = results[0]
            location = Place(
                name=first["SEARCHVAL"],
                place_type="location",
                address=first["ADDRESS"],
                postal_code=first["POSTAL"],
                latitude=float(first["LATITUDE"]),
                longitude=float(first["LONGITUDE"]),
            )
        except (IndexError, KeyError, TypeError, ValueError):
            return LocationSearchResult(
                status=SearchStatus.API_ERROR,
                message="Invalid OneMap response.",
            )
        return LocationSearchResult(status=SearchStatus.SUCCESS, location=location)

    def reverse_geocode(self, latitude: float, longitude: float) -> LocationSearchResult:
        token = self.authenticate()
        if token is None or not self.base_url:
            return LocationSearchResult(
                status=SearchStatus.API_ERROR,
                message="Unable to authenticate with OneMap.",
            )

        try:
            response = httpx.get(
                f"{self.base_url}/api/public/revgeocode",
                params={
                    "location": f"{latitude},{longitude}",
                    "buffer": 100,
                    "addressType": "All",
                },
                headers={"Authorization": token},
                timeout=self.timeout,
            )
            response.raise_for_status()
            first = response.json().get("GeocodeInfo", [])[0]
            building = str(first.get("BUILDINGNAME") or "").strip()
            road = str(first.get("ROAD") or "").strip()
            block = str(first.get("BLOCK") or "").strip()
            postal_code = str(first.get("POSTALCODE") or "").strip()
            name = building if building not in {"", "NIL", "null"} else road
            address = " ".join(part for part in (block, road) if part not in {"", "NIL"})
            location = Place(
                name=name or "Current location",
                place_type="browser_location",
                address=address or None,
                postal_code=postal_code if postal_code not in {"", "NIL"} else None,
                latitude=latitude,
                longitude=longitude,
            )
        except (httpx.RequestError, httpx.HTTPStatusError, IndexError, AttributeError, TypeError, ValueError):
            return LocationSearchResult(
                status=SearchStatus.API_ERROR,
                message="Unable to resolve the supplied coordinates.",
            )

        return LocationSearchResult(status=SearchStatus.SUCCESS, location=location)
