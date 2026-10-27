from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

PRODUCT_AKANG = "安康住院2024"
TENANT = "anlan-chengdu"


class Policy(BaseModel):
    policy_no: str
    status: str
    product: str
    issue_date: date
    hospitals: list[str]
    limit_amount: int
    insured_name: str = ""


class Claim(BaseModel):
    claim_id: str
    policy_no: str
    product: str
    admission: date
    discharge: date | None = None
    hospital: str
    amount: int
    documents: dict[str, Any] = Field(default_factory=dict)
    diagnosis_text: str = ""


class Suggestion(BaseModel):
    decision: str
    clause_ids: list[str] = Field(default_factory=list)
    rationale: str = ""
    model_calls: int = 0
    rule_ids: list[str] = Field(default_factory=list)
    missing_docs: list[str] = Field(default_factory=list)


class DeskRequest(BaseModel):
    claim_id: str
    intent: str
    actor_id: str = ""
