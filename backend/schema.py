# backend/schema.py
from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ---------- Companies ----------
class CompanyIn(BaseModel):
    name: str = Field(..., description="Nom de l'entreprise")
    variants: List[str] = Field(default_factory=list, description="Variantes / mots-clés liés à l'entreprise")
    competitors: List[str] = Field(default_factory=list, description="Concurrents de l'entreprise")


class CompanyOut(CompanyIn):
    id: int


# ---------- Campaigns ----------
class CampaignCreate(BaseModel):
    company_id: int
    prompts: List[str]
    runs_per_prompt: int = 10
    model: str = "llama3.2:1b-instruct"


# Alias pour rester compatible avec du code qui ferait `from ..schema import CampaignIn`
CampaignIn = CampaignCreate


class CampaignOut(BaseModel):
    id: int
    status: str = "queued"
    total_runs: int = 0
    completed_runs: int = 0
    visibility: float = 0.0


# ---------- Exports ----------
class ExportOut(BaseModel):
    campaign_id: int
    filename: str
    url: str                                # ex: "/exports/{campaign_id}.csv"
    size: Optional[int] = None              # octets
    content_type: str = "text/csv"
    created_at: Optional[datetime] = None
