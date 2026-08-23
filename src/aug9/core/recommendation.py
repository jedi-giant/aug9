from pydantic import BaseModel

from aug9.core.models import Place


class Recommendation(BaseModel):
    title: str
    reason: str
    places: list[Place] = []
    actions: list[str] = []
