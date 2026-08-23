from pydantic import BaseModel
from aug9.core.models import Place


class UserMemory(BaseModel):
    value: str
    memory_type: str
    confidence: float
    expires: bool = False


class ConversationState(BaseModel):
    current_place: Place | None = None
    last_intent: str | None = None
    history: list[str] = []
    preferences: dict[str, list[UserMemory]] = {}
