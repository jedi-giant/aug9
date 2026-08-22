import os
import sys
import httpx
from dotenv import load_dotenv
from aug9.onemap import get_token, search_location
from aug9.models import SearchStatus, Settings

def main() -> None:
    load_dotenv()

settings = Settings(
    onemap_email = os.getenv("ONEMAP_EMAIL"),
    onemap_password = os.getenv("ONEMAP_PASSWORD"),
    onemap_base_url = os.getenv("ONEMAP_BASE_URL"),
)

    if len(sys.argv) < 2:
        print("Please provide a location.")
        return

    query = " ".join(sys.argv[1:])

    token = get_token(base_url, email, password)

    result = search_location(
        base_url,
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
