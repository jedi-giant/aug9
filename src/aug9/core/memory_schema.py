from pydantic import BaseModel


class ExtractedMemory(BaseModel):
    category: str
    value: str
    memory_type: str
    confidence: float
    expires: bool = False


class MemoryExtractionResult(BaseModel):
    memories: list[ExtractedMemory]
