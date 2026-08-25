from aug9.models import LocationSearchResult
from aug9.sg_place.provider import OneMapProvider

def get_token(base_url: str, email: str, password: str) -> str | None:
    return OneMapProvider(base_url, email, password).authenticate()
    
def search_location(
    base_url: str,
    token: str,
    query: str,
) -> LocationSearchResult:
    return OneMapProvider(base_url, None, None).search_with_token(query, token)
    
