from aug9.core.models import Place
from aug9.models import WeatherResult
from aug9.sg_weather.provider import DataGovSgWeatherProvider


def get_weather(place: Place) -> WeatherResult:
    return DataGovSgWeatherProvider().forecast(place)
