import os

from dotenv import load_dotenv
from mcp.server import MCPServer

from aug9.models import SearchStatus
from aug9.onemap import get_token, search_location
from aug9.weather import get_weather
from aug9.transport import get_sg_route
from aug9.food import get_food_recommendations

mcp = MCPServer("Aug9")

@mcp.tool()
def get_sg_food(
    location: str,
) -> dict:

    result = get_food_recommendations(
        location
    )

    return result.model_dump()

@mcp.tool()
def get_sg_transport(
    origin: str,
    destination: str,
) -> dict:

    load_dotenv()

    token = get_token(
        os.getenv("ONEMAP_BASE_URL"),
        os.getenv("ONEMAP_EMAIL"),
        os.getenv("ONEMAP_PASSWORD"),
    )

    result = get_sg_route(
        os.getenv("ONEMAP_BASE_URL"),
        token,
        origin,
        destination,
    )

    return result.model_dump()

@mcp.tool()
def get_sg_weather(query: str) -> dict:
    load_dotenv()

    email = os.getenv("ONEMAP_EMAIL")
    password = os.getenv("ONEMAP_PASSWORD")
    base_url = os.getenv("ONEMAP_BASE_URL")

    token = get_token(
        base_url,
        email,
        password,
    )

    if token is None:
        return {
            "status": "authentication_error",
            "message": "Unable to authenticate with OneMap.",
        }

    location_result = search_location(
        base_url,
        token,
        query,
    )

    if location_result.status != SearchStatus.SUCCESS:
        return {
            "status": location_result.status.value,
            "message": location_result.message,
        }

    weather_result = get_weather(
        location_result.location
    )

    if weather_result.status != SearchStatus.SUCCESS:
        return {
            "status": weather_result.status.value,
            "message": weather_result.message,
        }

    return {
        "status": "success",
        "location": location_result.location.model_dump(),
        "weather": weather_result.weather.model_dump(),
    }

@mcp.tool()
def resolve_sg_location(query: str) -> dict:
    load_dotenv()

    email = os.getenv("ONEMAP_EMAIL")
    password = os.getenv("ONEMAP_PASSWORD")
    base_url = os.getenv("ONEMAP_BASE_URL")

    token = get_token(
        base_url,
        email,
        password,
    )

    if token is None:
        return {
            "status": "authentication_error",
            "message": "Unable to authenticate with OneMap.",
        }

    result = search_location(
        base_url,
        token,
        query,
    )

    if result.status == SearchStatus.SUCCESS:
        return {
            "status": "success",
            "location": result.location.model_dump(),
        }

    return {
        "status": result.status.value,
        "message": result.message,
    }
