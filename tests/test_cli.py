from unittest.mock import patch

from aug9.cli import main
from aug9.core.models import Place
from aug9.models import LocationSearchResult, SearchStatus

@patch("aug9.cli.search_location")
@patch("aug9.cli.get_token")
@patch("sys.argv", ["aug9", "Maxwell Food Centre"])
def test_main_prints_location(mock_get_token, mock_search_location, capsys):
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

    main()

    captured = capsys.readouterr()

    assert "MAXWELL FOOD CENTRE" in captured.out

@patch("aug9.cli.search_location")
@patch("aug9.cli.get_token")
@patch("sys.argv", ["aug9", "xyzabcnotaplace123"])
def test_main_prints_no_results(mock_get_token, mock_search_location, capsys):
    mock_get_token.return_value = "fake-token"

    mock_search_location.return_value = LocationSearchResult(
        status=SearchStatus.NO_RESULTS,
        message='No location found for "xyzabcnotaplace123".',
    )

    main()

    captured = capsys.readouterr()

    assert 'No location found for "xyzabcnotaplace123".' in captured.out

@patch("aug9.cli.search_location")
@patch("aug9.cli.get_token")
@patch("sys.argv", ["aug9", "Maxwell Food Centre"])
def test_main_prints_network_error(mock_get_token, mock_search_location, capsys):
    mock_get_token.return_value = "fake-token"

    mock_search_location.return_value = LocationSearchResult(
        status=SearchStatus.NETWORK_ERROR,
        message="Network unavailable",
    )

    main()

    captured = capsys.readouterr()

    assert "Network problem: Network unavailable" in captured.out
