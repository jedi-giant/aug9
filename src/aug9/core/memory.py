from typing import Any

from pydantic import BaseModel, Field
from aug9.core.models import Place


class UserMemory(BaseModel):
    value: str
    memory_type: str
    confidence: float
    expires: bool = False


class JourneyState(BaseModel):
    """Bounded, serialisable state for a multi-turn Singapore journey."""

    schema_version: int = 1
    journey_type: str
    original_intent: str
    requested_capabilities: list[str] = Field(default_factory=list)
    resolved_slots: dict[str, Any] = Field(default_factory=dict)
    pending_slots: list[str] = Field(default_factory=list)
    selected_stops: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "clarifying"


class ConversationState(BaseModel):
    current_place: Place | None = None
    last_intent: str | None = None
    history: list[str] = Field(default_factory=list)
    preferences: dict[str, list[UserMemory]] = Field(default_factory=dict)
    journey: JourneyState | None = None
