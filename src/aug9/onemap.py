import os
import time

from aug9.models import LocationSearchResult
from aug9.sg_place.provider import OneMapProvider


_token_cache: dict[tuple[str, str], tuple[str, float]] = {}
_location_cache: dict[tuple[str, str], tuple[LocationSearchResult, float]] = {}


def clear_token_cache() -> None:
    _token_cache.clear()


def clear_location_cache() -> None:
    _location_cache.clear()

def get_token(base_url: str, email: str, password: str) -> str | None:
    cache_key = (base_url, email)
    cached = _token_cache.get(cache_key)
    now = time.monotonic()
    if cached is not None and cached[1] > now:
        return cached[0]

    token = OneMapProvider(base_url, email, password).authenticate()
    if token is not None:
        ttl_seconds = max(60, int(os.getenv("ONEMAP_TOKEN_CACHE_SECONDS", "1800")))
        _token_cache[cache_key] = (token, now + ttl_seconds)
    return token
    
def search_location(
    base_url: str,
    token: str,
    query: str,
) -> LocationSearchResult:
    cache_key = (base_url, query.strip().casefold())
    cached = _location_cache.get(cache_key)
    now = time.monotonic()
    if cached is not None and cached[1] > now:
        return cached[0].model_copy(deep=True)

    result = OneMapProvider(base_url, None, None).search_with_token(query, token)
    if result.location is not None:
        ttl_seconds = max(
            60,
            int(os.getenv("ONEMAP_LOCATION_CACHE_SECONDS", "86400")),
        )
        _location_cache[cache_key] = (result.model_copy(deep=True), now + ttl_seconds)
    return result
    
