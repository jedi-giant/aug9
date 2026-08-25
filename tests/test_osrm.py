from unittest.mock import Mock, patch

from aug9.osrm import get_walking_route
from aug9.routing import calculate_route


@patch("aug9.osrm.httpx.get")
def test_get_walking_route(mock_get):
    mock_response = Mock()

    mock_response.json.return_value = {
        "code": "Ok",
        "routes": [
            {
                "legs": [
                    {
                        "steps": [
                            {
                                "name": "South Bridge Road"
                            },
                            {
                                "name": "Bayfront Avenue"
                            },
                        ]
                    }
                ]
            }
        ],
    }

    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = get_walking_route(
        1.280331,
        103.844747,
        1.2838,
        103.8591,
    )

    assert result["code"] == "Ok"
    assert len(result["routes"]) == 1


@patch("aug9.routing.get_walking_route")
def test_calculate_route_uses_public_string_model(mock_get_walking_route):
    mock_get_walking_route.return_value = {
        "routes": [
            {
                "distance": 1800,
                "duration": 1440,
                "legs": [{"steps": [{"name": "Bayfront Avenue"}]}],
            }
        ]
    }

    result = calculate_route(
        1.280331,
        103.844747,
        1.2838,
        103.8591,
        "Maxwell Food Centre",
        "Marina Bay Sands",
    )

    assert result.route is not None
    assert result.route.origin == "Maxwell Food Centre"
    assert result.route.destination == "Marina Bay Sands"
