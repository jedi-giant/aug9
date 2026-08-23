from pydantic import BaseModel


class RankedMemory(BaseModel):
    value: str
    relevance_score: float
    reason: str


class MemoryRankingResult(BaseModel):
    memories: list[RankedMemory]
