from unittest.mock import patch

from aug9.core.agent import run_aug9


@patch("aug9.core.context_builder.get_token")
@patch("aug9.core.context_builder.search_location")
def test_aug9_full_flow(
    mock_search,
    mock_token,
):

    mock_token.return_value = "fake-token"

    from aug9.models import (
        LocationSearchResult,
        SearchStatus,
    )
    from aug9.core.models import Place

    mock_search.return_value = LocationSearchResult(
        status=SearchStatus.SUCCESS,
        location=Place(
            name="MAXWELL FOOD CENTRE",
            place_type="location",
            address="1 KADAYANALLUR STREET",
            postal_code="069184",
            latitude=1.280331,
            longitude=103.844747,
        ),
    )

    response = run_aug9(
        "What should I eat at Maxwell Food Centre?"
    )

    assert "Tian Tian" in response
