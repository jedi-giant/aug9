from pydantic import BaseModel, Field


class PlanEntities(BaseModel):
    location: str | None = None
    origin: str | None = None
    destination: str | None = None
    category: str | None = None
    service_query: str | None = None
    plan_type: str | None = None
    travel_mode: str | None = None
    budget_sgd: float | None = None
    meal_type: str | None = None
    dietary_preferences: list[str] = Field(default_factory=list)
    open_now: bool = False
    child_ages: list[int] = Field(default_factory=list)
    water_play: bool = False
    sheltered: bool = False


class LLMPlan(BaseModel):
    intent: str
    required_capabilities: list[str]
    entities: PlanEntities
