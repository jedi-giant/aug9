from aug9.core.models import Place


def location_to_place(
    location,
) -> Place:

    return Place(
        name=location.name,
        place_type="location",
        address=location.address,
        postal_code=location.postal_code,
        latitude=location.latitude,
        longitude=location.longitude,
    )
