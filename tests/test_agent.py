import asyncio
import pytest

from aug9.agent import run_agent

@pytest.mark.integration
def test_agent_gets_weather_for_location():
    result = asyncio.run(
        run_agent(
            "What is the weather at Maxwell Food Centre?"
        )
    )

    assert "Maxwell" in result
    assert any(
        word in result.lower()
        for word in [
            "windy",
            "cloudy",
            "rain",
            "showers",
            "sunny",
            "weather",
        ]
    )

@pytest.mark.integration
def test_agent_resolves_valid_location():
    result = asyncio.run(
        run_agent("What is the postal code of Maxwell Food Centre?")
    )

    assert "069184" in result

@pytest.mark.integration
def test_agent_does_not_hallucinate_invalid_location():
    result = asyncio.run(
        run_agent("Where is XYZABCNOT123?")
    )

    assert "couldn’t" in result.lower() or "could not" in result.lower()

@pytest.mark.integration
def test_agent_gets_route_between_locations():
    result = asyncio.run(
        run_agent(
            "How do I get from Maxwell Food Centre to Marina Bay Sands?"
        )
    )

    assert "Maxwell" in result
    assert "Marina Bay Sands" in result
    assert any(
        word in result.lower()
        for word in [
            "walk",
            "route",
            "minute",
            "distance",
        ]
    )
