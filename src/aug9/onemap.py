import httpx

from aug9.core.models import Place
from aug9.models import LocationSearchResult, SearchStatus

def get_token(base_url: str, email: str, password: str) -> str | None:
    try:
        response = httpx.post(
            f"{base_url}/api/auth/post/getToken",
            json={
                "email": email,
                "password": password,
            },
            timeout=10.0,
        )

        response.raise_for_status()

    except httpx.RequestError:
        return None

    except httpx.HTTPStatusError:
        return None

    data = response.json()

    return data.get("access_token")
    
def search_location(
    base_url: str,
    token: str,
    query: str,
) -> LocationSearchResult:
    params = {
        "searchVal": query,
        "returnGeom": "Y",
        "getAddrDetails": "Y",
        "pageNum": 1,
    }
    
    try:
        response = httpx.get(
            f"{base_url}/api/common/elastic/search",
            params=params,
            headers={
                "Authorization": token,
            },
            timeout=10.0,
        )
    
        response.raise_for_status()
        
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
    data = response.json()
    results = data.get("results", [])
     
    if not results:
        simplified_query = query.replace(", Singapore", "").replace(" Singapore", "").strip()

        if simplified_query != query:
            return search_location(
                base_url=base_url,
                token=token,
                query=simplified_query,
            )

        return LocationSearchResult(
            status=SearchStatus.NO_RESULTS,
            message=f'No location found for "{query}".',
        )

    first = results[0]

    place = Place(
        name=first["SEARCHVAL"],
        place_type="location",
        address=first["ADDRESS"],
        postal_code=first["POSTAL"],
        latitude=float(first["LATITUDE"]),
        longitude=float(first["LONGITUDE"]),
    )

    return LocationSearchResult(
        status=SearchStatus.SUCCESS,
        location=place,
    )        
    
