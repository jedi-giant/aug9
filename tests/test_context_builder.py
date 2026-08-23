from unittest.mock import patch

from aug9.core.context_builder import build_context
from aug9.models import (
    LocationSearchResult,
    SearchStatus,
)

from aug9.core.models import Place

@patch("aug9.core.context_builder.search_location")
@patch("aug9.core.context_builder.get_token")
def test_build_context_resolves_location(
    mock_token,
    mock_search,
):

    mock_token.return_value = "fake-token"

    mock_search.return_value = LocationSearchResult(
        status=SearchStatus.SUCCESS,
        location=Place(
            name="MAXWELL FOOD CENTRE",
            place_type="location",
            address="1 KADAYANALLUR STREET",
            postal_code="069184",
            latitude=1.280331,
            longitude=103.844747,
        )
    )

    context = build_context(
        "What should I eat at Maxwell Food Centre?"
    )

    assert (
        context.current_place.name
        == "MAXWELL FOOD CENTRE"
    )
