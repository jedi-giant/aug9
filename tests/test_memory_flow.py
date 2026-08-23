from aug9.core.session import (
    get_memory,
    update_memory,
)
from aug9.core.memory import ConversationState
from aug9.core.models import Place


def test_previous_location_is_remembered():

    place = Place(
        name="Maxwell Food Centre",
        place_type="hawker_centre",
        address="1 Kadayanallur Street",
        postal_code="069184",
        latitude=1.280331,
        longitude=103.844747,
    )

    update_memory(
        ConversationState(
            current_place=place
        )
    )

    memory = get_memory()

    assert (
        memory.current_place.name
        == "Maxwell Food Centre"
    )
