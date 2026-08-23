from pydantic import BaseModel

from aug9.core.models import Place

from aug9.core.memory import ConversationState


class UserContext(BaseModel):
    current_place: Place | None = None
    intent: str | None = None
    preferences: list[str] = []
    memory: ConversationState | None = None
