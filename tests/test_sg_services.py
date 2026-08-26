from aug9.core.context import UserContext
from aug9.sg_services import OfficialGovernmentServiceProvider, SgServicesSkill
import pytest


def test_official_provider_matches_passport_service():
    services = OfficialGovernmentServiceProvider().search("How do I renew my passport?")

    assert services[0].agency == "Immigration & Checkpoints Authority"
    assert str(services[0].url) == "https://www.ica.gov.sg/documents/passport/apply"
    assert len(services) == 1


def test_services_skill_returns_structured_official_actions():
    result = SgServicesSkill(OfficialGovernmentServiceProvider()).execute(
        UserContext(intent="Help me with my CPF account"), {}
    )

    assert result.success is True
    assert result.data["services"][0]["agency"] == "Central Provident Fund Board"
    assert result.actions[0].metadata["capability"] == "services"
    assert result.actions[0].url.startswith("https://www.cpf.gov.sg/")
    assert len(result.actions) == 1


def test_services_skill_falls_back_to_lifesg_for_unknown_request():
    result = SgServicesSkill(OfficialGovernmentServiceProvider()).execute(
        UserContext(intent="Help with a very unusual matter called xyzzy"), {}
    )

    assert result.success is False
    assert result.actions[0].url == "https://www.life.gov.sg/"


@pytest.mark.parametrize(
    ("query", "agency"),
    [
        ("I need to replace my NRIC", "Immigration & Checkpoints Authority"),
        ("How do I register my newborn's birth?", "Immigration & Checkpoints Authority"),
        ("How can we get married?", "Registry of Marriages"),
        ("Replace my driving licence", "Singapore Police Force"),
        ("National Service registration", "Ministry of Defence"),
        ("Primary 1 registration", "Ministry of Education"),
        ("I want to start a business", "GoBusiness Singapore"),
    ],
)
def test_expanded_service_topics_return_official_agency(query, agency):
    services = OfficialGovernmentServiceProvider().search(query)

    assert services
    assert services[0].agency == agency
