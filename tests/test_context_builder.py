from unittest.mock import patch

from aug9.core.context_builder import build_context
from aug9.models import (
    LocationSearchResult,
    SearchStatus,
)

from aug9.core.models import Place
from aug9.core.memory import ConversationState

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


@patch("aug9.core.context_builder.get_memory")
@patch("aug9.core.context_builder.update_memory")
@patch("aug9.core.context_builder.search_location")
@patch("aug9.core.context_builder.get_token", return_value="fake-token")
def test_build_context_reuses_loaded_memory_without_database_reload(
    _mock_token, mock_search, mock_update, mock_get_memory
):
    loaded_memory = ConversationState(history=["Earlier request"])
    mock_search.return_value = LocationSearchResult(
        status=SearchStatus.SUCCESS,
        location=Place(name="MAXWELL FOOD CENTRE"),
    )

    context = build_context(
        "Weather at Maxwell Food Centre",
        {"location": "Maxwell Food Centre"},
        user_id="user",
        memory=loaded_memory,
    )

    mock_get_memory.assert_not_called()
    mock_update.assert_called_once()
    assert mock_update.call_args.kwargs["persist"] is False
    assert context.memory.history == ["Earlier request", "Weather at Maxwell Food Centre"]
