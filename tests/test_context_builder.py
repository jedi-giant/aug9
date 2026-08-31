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


@patch("aug9.core.context_builder.OneMapProvider.from_environment")
@patch("aug9.core.context_builder.get_memory")
@patch("aug9.core.context_builder.search_location")
@patch("aug9.core.context_builder.get_token")
def test_supplied_browser_place_bypasses_lookup_and_is_not_persisted(
    mock_token, mock_search, mock_get_memory, mock_provider_factory
):
    memory = ConversationState()
    supplied = Place(
        name="Current location",
        place_type="browser_location",
        latitude=1.2903,
        longitude=103.8519,
    )
    mock_provider_factory.return_value.reverse_geocode.return_value = LocationSearchResult(
        status=SearchStatus.SUCCESS,
        location=Place(
            name="MARINA BAY SANDS",
            place_type="browser_location",
            address="10 BAYFRONT AVENUE",
            postal_code="018956",
            latitude=1.2903,
            longitude=103.8519,
        ),
    )

    context = build_context(
        "Find food near me",
        user_id="visitor",
        memory=memory,
        supplied_place=supplied,
    )

    assert context.current_place.name == "MARINA BAY SANDS"
    assert context.current_place.postal_code == "018956"
    assert context.memory.current_place.name == "MARINA BAY SANDS"
    assert context.memory.history == ["Find food near me"]
    mock_token.assert_not_called()
    mock_search.assert_not_called()
    mock_get_memory.assert_not_called()
