from pydantic import BaseModel

from aug9.core.models import Place


class UserContext(BaseModel):
    current_place: Place | None = None
    intent: str | None = None
    preferences: list[str] = []
