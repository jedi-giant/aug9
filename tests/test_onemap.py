import httpx

from unittest.mock import Mock, patch

from aug9.onemap import search_location
from aug9.onemap import clear_token_cache, get_token, search_location
from aug9.models import SearchStatus

@patch("aug9.sg_place.provider.httpx.get")
def test_search_location_retries_without_singapore_suffix(mock_get):
    first_response = Mock()
    first_response.json.return_value = {
        "results": []
    }
    first_response.raise_for_status.return_value = None

    second_response = Mock()
    second_response.json.return_value = {
        "results": [
            {
                "SEARCHVAL": "MAXWELL FOOD CENTRE",
                "ADDRESS": "1 KADAYANALLUR STREET MAXWELL FOOD CENTRE SINGAPORE 069184",
                "POSTAL": "069184",
                "LATITUDE": "1.28033142727315",
                "LONGITUDE": "103.844747227479",
            }
        ]
    }
    second_response.raise_for_status.return_value = None

    mock_get.side_effect = [
        first_response,
        second_response,
    ]

    result = search_location(
        base_url="https://example.com",
        token="fake-token",
        query="Maxwell Food Centre, Singapore",
    )

    assert result.status == SearchStatus.SUCCESS
    assert result.location is not None
    assert result.location.name == "MAXWELL FOOD CENTRE"
    assert mock_get.call_count == 2

@patch("aug9.sg_place.provider.httpx.post")
def test_get_token_returns_none_on_http_error(mock_post):
    clear_token_cache()
    mock_response = Mock()
    mock_response.status_code = 401

    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Unauthorized",
        request=Mock(),
        response=mock_response,
    )

    mock_post.return_value = mock_response

    token = get_token(
        base_url="https://example.com",
        email="test@example.com",
        password="wrong-password",
    )

    assert token is None

@patch("aug9.sg_place.provider.httpx.post")
def test_get_token_returns_token(mock_post):
    clear_token_cache()
    mock_response = Mock()

    mock_response.json.return_value = {
        "access_token": "fake-token"
    }

    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    token = get_token(
        base_url="https://example.com",
        email="test@example.com",
        password="password",
    )

    assert token == "fake-token"

    assert get_token(
        base_url="https://example.com",
        email="test@example.com",
        password="password",
    ) == "fake-token"
    assert mock_post.call_count == 1

@patch("aug9.sg_place.provider.httpx.post")
def test_get_token_returns_none_on_network_error(mock_post):
    clear_token_cache()
    mock_post.side_effect = httpx.RequestError(
        "Network unavailable"
    )

    token = get_token(
        base_url="https://example.com",
        email="test@example.com",
        password="password",
    )

    assert token is None

@patch("aug9.sg_place.provider.httpx.get")
def test_search_location_returns_location(mock_get):
    mock_response = Mock()

    mock_response.json.return_value = {
        "results": [
            {
                "SEARCHVAL": "MAXWELL FOOD CENTRE",
                "ADDRESS": "1 KADAYANALLUR STREET MAXWELL FOOD CENTRE SINGAPORE 069184",
                "POSTAL": "069184",
                "LATITUDE": "1.28033142727315",
                "LONGITUDE": "103.844747227479",
            }
        ]
    }

    mock_response.raise_for_status.return_value = None

    mock_get.return_value = mock_response

    result = search_location(
        base_url="https://example.com",
        token="fake-token",
        query="Maxwell Food Centre",
    )

    assert result.status == SearchStatus.SUCCESS
    assert result.location is not None
    assert result.location.name == "MAXWELL FOOD CENTRE"
    assert result.location.postal_code == "069184"
    assert isinstance(result.location.latitude, float)

@patch("aug9.sg_place.provider.httpx.get")
def test_search_location_returns_none_when_no_results(mock_get):
    mock_response = Mock()

    mock_response.json.return_value = {
        "results": []
    }

    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = search_location(
        base_url="https://example.com",
        token="fake-token",
        query="Not A Real Place",
    )

    assert result.status == SearchStatus.NO_RESULTS
    assert result.location is None

@patch("aug9.sg_place.provider.httpx.get")
def test_search_location_returns_none_on_network_error(mock_get):
    mock_get.side_effect = httpx.RequestError(
        "Network unavailable"
    )

    result = search_location(
        base_url="https://example.com",
        token="fake-token",
        query="Maxwell Food Centre",
    )

    assert result.status == SearchStatus.NETWORK_ERROR
    assert result.location is None
    assert result.message == "Network unavailable"
