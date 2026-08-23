from aug9.core.models import Place
from aug9.models import Location


def location_to_place(
    location: Location,
) -> Place:

    return Place(
        name=location.name,
        place_type="location",
        address=location.address,
        postal_code=location.postal_code,
        latitude=location.latitude,
        longitude=location.longitude,
    )
