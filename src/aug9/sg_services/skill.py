from typing import Any

from aug9.core.context import UserContext
from aug9.core.skill import Aug9Skill, SkillAction, SkillResult
from aug9.sg_services.provider import GovernmentServiceProvider


class SgServicesSkill(Aug9Skill):
    name = "sg_services"
    description = "Find official Singapore government services"
    version = "0.1.0"

    def __init__(self, provider: GovernmentServiceProvider) -> None:
        self.provider = provider

    @property
    def capabilities(self) -> list[str]:
        return ["services"]

    def execute(self, context: UserContext, entities: dict[str, Any]) -> SkillResult:
        query = str(entities.get("service_query") or context.intent or "")
        services = self.provider.search(query)
        if not services:
            return SkillResult(
                success=False,
                summary=(
                    "I could not identify a matching government service. "
                    "Use LifeSG to browse official Singapore services."
                ),
                actions=[
                    SkillAction(
                        type="open_url",
                        label="Browse services on LifeSG",
                        url="https://www.life.gov.sg/",
                        metadata={"capability": "services", "agency": "LifeSG"},
                    )
                ],
            )
        return SkillResult(
            success=True,
            data={
                "services": [service.model_dump(mode="json") for service in services],
                "notice": "Requirements can change; verify details on the official page.",
            },
            summary="Official services: " + ", ".join(item.name for item in services) + ".",
            actions=[
                SkillAction(
                    type="open_url",
                    label=f"Open {service.name}",
                    url=str(service.url),
                    metadata={"capability": "services", "agency": service.agency},
                )
                for service in services
            ],
        )
