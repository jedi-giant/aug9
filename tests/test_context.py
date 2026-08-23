from aug9.core.context import UserContext
from aug9.core.models import Place


def test_user_context():

    context = UserContext(
        current_place=Place(
            name="Maxwell Food Centre",
            place_type="hawker_centre",
        ),
        intent="lunch",
        preferences=[
            "local food"
        ],
    )

    assert context.intent == "lunch"
    assert context.current_place.name == "Maxwell Food Centre"
