import os
import sys
from dotenv import load_dotenv
from aug9.onemap import get_token, search_location
from aug9.models import SearchStatus, Settings
from pydantic import ValidationError

def main() -> None:
    load_dotenv()
    try:
        settings = Settings(
            onemap_email = os.getenv("ONEMAP_EMAIL"),
            onemap_password = os.getenv("ONEMAP_PASSWORD"),
            onemap_base_url = os.getenv("ONEMAP_BASE_URL"),
        )
    except ValidationError:
    
        print("Configuration error: OneMap credentials are missing.")
        return

    if len(sys.argv) < 2:
        print("Please provide a location.")
        return

    query = " ".join(sys.argv[1:])

    token = get_token(
        settings.onemap_base_url,
        settings.onemap_email,
        settings.onemap_password,
    )

    if token is None:
        print("Authentication error: Unable to authenticate with OneMap.")
        return

    result = search_location(
        settings.onemap_base_url,
        token,
        query,
    )
    
    result = search_location(
        settings.onemap_base_url,
        token,
        query,
    )

    if result.status == SearchStatus.SUCCESS:
        print(result.location)
        return

    if result.status == SearchStatus.NO_RESULTS:
        print(result.message)
        return

    if result.status == SearchStatus.NETWORK_ERROR:
        print("Network problem:", result.message)
        return

    if result.status == SearchStatus.API_ERROR:
        print("OneMap API problem:", result.message)
        return
