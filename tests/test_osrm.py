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
    assert result.route.duration_minutes == 22.5


@patch("aug9.routing.get_walking_route")
def test_calculate_route_deduplicates_steps_and_ignores_motor_timing(
    mock_get_walking_route,
):
    mock_get_walking_route.return_value = {
        "routes": [
            {
                "distance": 6400,
                "duration": 600,
                "legs": [
                    {
                        "steps": [
                            {"name": "Ann Siang Road"},
                            {"name": "Ann Siang Road"},
                            {"name": "Club Street"},
                        ]
                    }
                ],
            }
        ]
    }

    result = calculate_route(1.28, 103.84, 1.31, 103.82, "Maxwell", "RELC")

    assert result.route.duration_minutes == 80.0
    assert result.route.steps == ["Ann Siang Road", "Club Street"]
    assert "about 80 minutes" in result.route.summary
