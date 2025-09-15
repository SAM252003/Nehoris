from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, JSON

class Company(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    variants: List[str] = Field(sa_column=Column(JSON), default_factory=list)
    competitors: List[str] = Field(sa_column=Column(JSON), default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Prompt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    text: str


class Campaign(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id")
    model: str = "perplexity:sonar"
    runs_per_query: int = 1
    temperature: float = 0.1
    total_prompts: int = 0
    completed_runs: int = 0
    status: str = "queued"  # queued|running|done|error
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CampaignPrompt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="campaign.id")
    prompt_id: int = Field(foreign_key="prompt.id")
    order_index: int = 0

class Run(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="campaign.id")
    prompt_id: int = Field(foreign_key="prompt.id")
    run_index: int = 0
    model: str
    text: str
    appear_answer: bool
    appear_lead: bool
    first_pos: int
    brand_hits: int
    comp_hits: dict = Field(sa_column=Column(JSON), default_factory=dict)
    sources: list = Field(sa_column=Column(JSON), default_factory=list)
    rankings: dict = Field(sa_column=Column(JSON), default_factory=dict)

    created_at: datetime = Field(default_factory=datetime.utcnow)

