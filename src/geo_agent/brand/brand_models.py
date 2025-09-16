from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel

class Brand(BaseModel):
    name: str
    variants: List[str] = []

class BrandMatch(BaseModel):
    brand: str
    variant: str
    start: int
    end: int
    score: float
    method: str  # "exact" | "fuzzy" | "llm"
    context: Optional[str] = None

class DetectRequest(BaseModel):
    text: str
    brands: List[Brand]
    fuzzy_threshold: float = 85.0
    use_llm_judge: bool = False

class DetectResponse(BaseModel):
    matches: List[BrandMatch]
