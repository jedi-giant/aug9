from typing import Protocol

from pydantic import BaseModel, HttpUrl


class GovernmentService(BaseModel):
    name: str
    agency: str
    description: str
    url: HttpUrl
    topics: tuple[str, ...]


class GovernmentServiceProvider(Protocol):
    def search(self, query: str, *, limit: int = 5) -> list[GovernmentService]: ...


OFFICIAL_SERVICES = (
    GovernmentService(
        name="Apply for or renew a Singapore passport",
        agency="Immigration & Checkpoints Authority",
        description="Official ICA information for Singapore passport applications.",
        url="https://www.ica.gov.sg/documents/passport/apply",
        topics=("passport", "renew passport", "travel document", "ica"),
    ),
    GovernmentService(
        name="Identity card services",
        agency="Immigration & Checkpoints Authority",
        description="Official ICA information for Singapore identity cards.",
        url="https://www.ica.gov.sg/documents/identity-cards",
        topics=("identity card", "nric", "replace ic", "register ic"),
    ),
    GovernmentService(
        name="Register a birth",
        agency="Immigration & Checkpoints Authority",
        description="Official information for registering a birth in Singapore.",
        url="https://www.ica.gov.sg/documents/birth/birth_registration",
        topics=("birth registration", "register birth", "birth certificate", "newborn"),
    ),
    GovernmentService(
        name="Civil marriage services",
        agency="Registry of Marriages",
        description="Official civil marriage process and application information.",
        url="https://www.marriage.gov.sg/civil/marriage-process",
        topics=("marriage", "get married", "register marriage", "rom", "solemnisation"),
    ),
    GovernmentService(
        name="Driving licence services",
        agency="Singapore Police Force",
        description="Official applications, renewals, and replacements for driving licences.",
        url="https://www.police.gov.sg/E-Services/Apply-for-Qualified-Driving-Licence",
        topics=("driving licence", "driver licence", "driving license", "qdl"),
    ),
    GovernmentService(
        name="National Service information",
        agency="Ministry of Defence",
        description="Official National Service information for pre-enlistees and parents.",
        url="https://www.mindef.gov.sg/national-service/discover-pre-enlistee-parent/",
        topics=("national service", "ns registration", "pre-enlistee", "enlistment"),
    ),
    GovernmentService(
        name="Primary 1 registration",
        agency="Ministry of Education",
        description="Official information about Primary 1 registration.",
        url="https://www.moe.gov.sg/primary/p1-registration",
        topics=("primary 1", "p1 registration", "school registration", "primary school"),
    ),
    GovernmentService(
        name="Start a business",
        agency="GoBusiness Singapore",
        description="Official guidance and services for starting a business in Singapore.",
        url="https://www.gobusiness.gov.sg/start-a-business/",
        topics=("start business", "starting a business", "register company", "incorporate company"),
    ),
    GovernmentService(
        name="Singpass help and services",
        agency="Government Technology Agency",
        description="Official Singpass support and account information.",
        url="https://www.singpass.gov.sg/main/",
        topics=("singpass", "singpass login", "digital identity"),
    ),
    GovernmentService(
        name="CPF member services",
        agency="Central Provident Fund Board",
        description="Official CPF information and online member services.",
        url="https://www.cpf.gov.sg/member",
        topics=("cpf", "retirement", "medisave", "central provident fund"),
    ),
    GovernmentService(
        name="Individual income tax services",
        agency="Inland Revenue Authority of Singapore",
        description="Official IRAS information for individual income tax matters.",
        url="https://www.iras.gov.sg/taxes/individual-income-tax",
        topics=("tax", "taxes", "income tax", "iras", "file tax"),
    ),
    GovernmentService(
        name="HDB flat and housing services",
        agency="Housing & Development Board",
        description="Official information about HDB flats and housing services.",
        url="https://www.hdb.gov.sg/residential",
        topics=("hdb", "flat", "housing", "bto", "resale"),
    ),
    GovernmentService(
        name="Employment practices and work passes",
        agency="Ministry of Manpower",
        description="Official employment-practice and work-pass information.",
        url="https://www.mom.gov.sg/",
        topics=("employment", "work pass", "work permit", "salary", "mom"),
    ),
    GovernmentService(
        name="HealthHub services",
        agency="Ministry of Health and Synapxe",
        description="Official access to Singapore health information and services.",
        url="https://www.healthhub.sg/",
        topics=("health", "healthcare", "medical", "appointment", "healthhub"),
    ),
    GovernmentService(
        name="LifeSG government services",
        agency="Government of Singapore",
        description="Official starting point for commonly used government services.",
        url="https://www.life.gov.sg/",
        topics=("government service", "government services", "lifesg"),
    ),
)


class OfficialGovernmentServiceProvider:
    """Searches a curated directory containing official government links only."""

    def __init__(self, services: tuple[GovernmentService, ...] = OFFICIAL_SERVICES):
        self.services = services

    def search(self, query: str, *, limit: int = 5) -> list[GovernmentService]:
        normalized_query = query.casefold()
        stop_words = {
            "about", "called", "help", "how", "matter", "the", "very", "what",
            "singapore", "where", "with",
        }
        terms = {
            term.strip(".,?!")
            for term in normalized_query.split()
            if len(term.strip(".,?!")) > 2 and term.strip(".,?!") not in stop_words
        }
        scored: list[tuple[int, GovernmentService]] = []
        for service in self.services:
            haystack = " ".join(
                (service.name, service.agency, service.description, *service.topics)
            ).casefold()
            phrase_score = sum(10 for topic in service.topics if topic in normalized_query)
            word_score = sum(1 for term in terms if term in haystack)
            score = phrase_score + word_score
            if score:
                scored.append((score, service))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        if not scored:
            return []
        relevance_floor = max(2, scored[0][0] - 2)
        return [
            service for score, service in scored if score >= relevance_floor
        ][:limit]
