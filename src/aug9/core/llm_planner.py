from pydantic import BaseModel, Field


class PlanEntities(BaseModel):
    location: str | None = None


class LLMPlan(BaseModel):
    intent: str
    required_capabilities: list[str]
    entities: PlanEntities
