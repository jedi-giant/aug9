from unittest.mock import Mock, patch

from aug9.osrm import get_walking_route


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
