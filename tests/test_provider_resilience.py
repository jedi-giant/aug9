from unittest.mock import Mock, patch

from aug9.core import llm
from aug9.core.models import Place
from aug9.models import SearchStatus
from aug9.sg_place.provider import OneMapProvider
from aug9.sg_weather.provider import DataGovSgWeatherProvider


@patch("aug9.core.llm.OpenAI")
def test_openai_client_uses_bounded_timeout_without_hidden_retries(
    mock_openai, monkeypatch
):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "9")
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "0")

    llm.build_client()

    mock_openai.assert_called_once_with(
        api_key="test",
        timeout=9.0,
        max_retries=0,
    )


@patch("aug9.sg_place.provider.httpx.post")
def test_onemap_authentication_contains_malformed_payload(mock_post):
    response = mock_post.return_value
    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("invalid json")

    assert OneMapProvider("https://example.com", "email", "password").authenticate() is None


@patch("aug9.sg_place.provider.httpx.get")
def test_onemap_search_contains_malformed_result(mock_get):
    response = mock_get.return_value
    response.raise_for_status.return_value = None
    response.json.return_value = {"results": [{"SEARCHVAL": "Broken"}]}

    result = OneMapProvider(
        "https://example.com", None, None
    ).search_with_token("Broken", "token")

    assert result.status == SearchStatus.API_ERROR
    assert result.message == "Invalid OneMap response."


@patch("aug9.sg_weather.provider.httpx.get")
def test_weather_provider_contains_malformed_payload(mock_get):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"data": {"items": []}}
    mock_get.return_value = response

    result = DataGovSgWeatherProvider().forecast(
        Place(name="Maxwell", latitude=1.28, longitude=103.84)
    )

    assert result.status == SearchStatus.API_ERROR
    assert result.message == "Invalid weather response."
