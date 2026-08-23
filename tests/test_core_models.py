from aug9.core.models import Place


def test_place_model():

    place = Place(
        name="Maxwell Food Centre",
        place_type="hawker_centre",
        postal_code="069184",
        latitude=1.280331,
        longitude=103.844747,
    )

    assert place.name == "Maxwell Food Centre"
    assert place.place_type == "hawker_centre"
