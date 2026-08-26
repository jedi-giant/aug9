from unittest.mock import Mock, patch

import httpx

from aug9.core.models import Place
from aug9.models import SearchStatus
from aug9.sg_weather.provider import DataGovSgWeatherProvider
from aug9.weather import get_weather

@patch("aug9.sg_weather.provider.httpx.get")
def test_get_weather_returns_network_error(mock_get):
    mock_get.side_effect = httpx.RequestError(
        "Network unavailable"
    )

    place = Place(
        name="MAXWELL FOOD CENTRE",
        place_type="location",
        address="1 KADAYANALLUR STREET",
        postal_code="069184",
        latitude=1.2803,
        longitude=103.8447,
    )

    result = get_weather(place)

    assert result.status == SearchStatus.NETWORK_ERROR
    assert result.message == "Network unavailable"

@patch("aug9.sg_weather.provider.httpx.get")
def test_get_weather_returns_api_error(mock_get):
    mock_response = Mock()

    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server error",
        request=Mock(),
        response=Mock(status_code=500),
    )

    mock_get.return_value = mock_response

    place = Place(
        name="MAXWELL FOOD CENTRE",
        place_type="location",
        address="1 KADAYANALLUR STREET",
        postal_code="069184",
        latitude=1.2803,
        longitude=103.8447,
    )

    result = get_weather(place)

    assert result.status == SearchStatus.API_ERROR
    assert "HTTP 500" in result.message

@patch("aug9.sg_weather.provider.httpx.get")
def test_get_weather_returns_forecast_for_nearest_area(mock_get):
    mock_response = Mock()

    mock_response.json.return_value = {
        "data": {
            "area_metadata": [
                {
                    "name": "Bukit Merah",
                    "label_location": {
                        "latitude": 1.277,
                        "longitude": 103.819,
                    },
                },
                {
                    "name": "Bedok",
                    "label_location": {
                        "latitude": 1.321,
                        "longitude": 103.924,
                    },
                },
            ],
            "items": [
                {
                    "forecasts": [
                        {
                            "area": "Bukit Merah",
                            "forecast": "Windy",
                        },
                        {
                            "area": "Bedok",
                            "forecast": "Cloudy",
                        },
                    ]
                }
            ],
        }
    }

    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    place = Place(
        name="MAXWELL FOOD CENTRE",
        place_type="location",
        address="1 KADAYANALLUR STREET",
        postal_code="069184",
        latitude=1.2803,
        longitude=103.8447,
    )

    provider = DataGovSgWeatherProvider()
    result = provider.forecast(place)

    assert result.status == SearchStatus.SUCCESS
    assert result.weather is not None
    assert result.weather.forecast == "Windy"

    cached = provider.forecast(place)
    assert cached.weather.forecast == "Windy"
    assert mock_get.call_count == 1
