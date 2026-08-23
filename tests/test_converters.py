from aug9.core.converters import location_to_place
from aug9.models import Location


def test_location_converts_to_place():

    location = Location(
        name="Maxwell Food Centre",
        address="1 Kadayanallur Street",
        postal_code="069184",
        latitude=1.280331,
        longitude=103.844747,
    )

    place = location_to_place(location)

    assert place.name == "Maxwell Food Centre"
    assert place.postal_code == "069184"
