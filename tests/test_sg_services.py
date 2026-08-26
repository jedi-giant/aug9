from aug9.core.context import UserContext
from aug9.sg_services import OfficialGovernmentServiceProvider, SgServicesSkill


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
