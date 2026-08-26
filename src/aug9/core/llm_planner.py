from pydantic import BaseModel, Field


class PlanEntities(BaseModel):
    location: str | None = None
    origin: str | None = None
    destination: str | None = None
    category: str | None = None
    service_query: str | None = None
    plan_type: str | None = None
    travel_mode: str | None = None


class LLMPlan(BaseModel):
    intent: str
    required_capabilities: list[str]
    entities: PlanEntities
