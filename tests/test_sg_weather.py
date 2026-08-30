from aug9.core.context import UserContext
from aug9.core.models import Place
from aug9.models import SearchStatus, Weather, WeatherResult
from aug9.sg_weather.skill import SgWeatherSkill


class FakeWeatherProvider:
    def __init__(self, result: WeatherResult) -> None:
        self.result = result
        self.places: list[Place] = []

    def forecast(self, place: Place) -> WeatherResult:
        self.places.append(place)
        return self.result


def test_sg_weather_returns_structured_forecast():
    provider = FakeWeatherProvider(
        WeatherResult(
            status=SearchStatus.SUCCESS,
            weather=Weather(forecast="Windy"),
        )
    )
    place = Place(name="Maxwell", latitude=1.28, longitude=103.84)

    result = SgWeatherSkill(provider).execute(UserContext(current_place=place), {})

    assert result.success is True
    assert result.data["weather"]["forecast"] == "Windy"
    assert provider.places == [place]


def test_sg_weather_requires_a_resolved_place():
    provider = FakeWeatherProvider(
        WeatherResult(status=SearchStatus.SUCCESS, weather=Weather(forecast="Fair"))
    )

    result = SgWeatherSkill(provider).execute(UserContext(), {})

    assert result.success is False
    assert result.summary == (
        "Which part of Singapore are you checking the weather for?"
    )
    assert provider.places == []


def test_sg_weather_preserves_provider_failure():
    provider = FakeWeatherProvider(
        WeatherResult(status=SearchStatus.NETWORK_ERROR, message="Unavailable")
    )

    result = SgWeatherSkill(provider).execute(
        UserContext(current_place=Place(name="Maxwell")),
        {},
    )

    assert result.success is False
    assert result.summary == (
        "Singapore weather information is temporarily unavailable. "
        "Please try again shortly."
    )
