from pydantic import BaseModel, Field


class PlanEntities(BaseModel):
    location: str | None = None
    origin: str | None = None
    destination: str | None = None
    category: str | None = None


class LLMPlan(BaseModel):
    intent: str
    required_capabilities: list[str]
    entities: PlanEntities
