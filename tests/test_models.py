from aug9.core.models import Place

def test_place_converts_coordinates_to_float():
    location = Place(
        name="Maxwell Food Centre",
        place_type="location",
        address="1 Kadayanallur Street",
        postal_code="069184",
        latitude="1.28033142727315",
        longitude="103.844747227479",
    )

    assert isinstance(location.latitude, float)
    assert isinstance(location.longitude, float)

import pytest
from pydantic import ValidationError


def test_place_rejects_invalid_latitude():
    with pytest.raises(ValidationError):
        Place(
            name="Bad Location",
            place_type="location",
            address="Unknown",
            postal_code="000000",
            latitude="not-a-number",
            longitude="103.8447",
        )
