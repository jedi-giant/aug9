from unittest.mock import patch

from aug9.mcp_server import resolve_sg_location
from aug9.core.models import Place
from aug9.models import LocationSearchResult, SearchStatus

@patch("aug9.mcp_server.get_token")
def test_resolve_sg_location_authentication_error(mock_get_token):
    mock_get_token.return_value = None

    result = resolve_sg_location("Maxwell Food Centre")

    assert result["status"] == "authentication_error"
    assert result["message"] == "Unable to authenticate with OneMap."

@patch("aug9.mcp_server.search_location")
@patch("aug9.mcp_server.get_token")
def test_resolve_sg_location_success(mock_get_token, mock_search_location):
    mock_get_token.return_value = "fake-token"

    mock_search_location.return_value = LocationSearchResult(
        status=SearchStatus.SUCCESS,
        location=Place(
            name="MAXWELL FOOD CENTRE",
            place_type="location",
            address="1 KADAYANALLUR STREET",
            postal_code="069184",
            latitude=1.2803,
            longitude=103.8447,
        ),
    )

    result = resolve_sg_location("Maxwell Food Centre")

    assert result["status"] == "success"
    assert result["location"]["postal_code"] == "069184"
