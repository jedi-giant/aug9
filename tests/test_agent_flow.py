from unittest.mock import patch

from aug9.core.agent import run_aug9
from aug9.core.memory_schema import MemoryExtractionResult


@patch(
    "aug9.core.agent.extract_memories",
    return_value=MemoryExtractionResult(memories=[]),
)
@patch("aug9.core.context_builder.get_token")
@patch("aug9.core.context_builder.search_location")
def test_aug9_full_flow(
    mock_search,
    mock_token,
    _mock_extract_memories,
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
        "What should I eat at Maxwell Food Centre?",
        user_id="test_user",
        session_id="test_session",
    )

    assert "Tian Tian" in response
    _mock_extract_memories.assert_not_called()
