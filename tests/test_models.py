from aug9.models import Location


def test_location_converts_coordinates_to_float():
    location = Location(
        name="Maxwell Food Centre",
        address="1 Kadayanallur Street",
        postal_code="069184",
        latitude="1.28033142727315",
        longitude="103.844747227479",
    )

    assert isinstance(location.latitude, float)
    assert isinstance(location.longitude, float)

import pytest
from pydantic import ValidationError


def test_location_rejects_invalid_latitude():
    with pytest.raises(ValidationError):
        Location(
            name="Bad Location",
            address="Unknown",
            postal_code="000000",
            latitude="not-a-number",
            longitude="103.8447",
        )
