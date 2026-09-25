"""Read-only response contracts. Secrets and raw file bytes are never response fields."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, JsonValue

from .schemas import Terms


class UserView(BaseModel):
    id: str
    name: str
    email: str
    role: str
    permissions: list[str]


class SessionTokens(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    expires_in: int
    user: UserView


class RuleResult(BaseModel):
    rule_id: str
    rule_name: str
    category: str
    severity: str
    status: Literal["PASS", "FAIL", "WARNING", "NOT_APPLICABLE", "MANUAL_REVIEW"]
    rule_version: int
    engine_version: str
    expected_value: str
    actual_value: str
    explanation: str
    evidence: list[dict[str, JsonValue]]
    recommendation: str


class RiskView(BaseModel):
    score: int = Field(ge=0, le=100)
    band: str
    factors: list[dict[str, JsonValue]]
    explanation: str


class ValidationView(BaseModel):
    id: str
    lc_id: str
    fingerprint: str
    results: list[RuleResult]
    risk: RiskView
    actor_id: str
    correlation_id: str
    created_at: datetime


class LCView(BaseModel):
    id: str
    reference: str
    title: str
    terms: Terms
    status: str
    priority: str
    created_by: str
    submitted_by: str | None
    reviewed_by: str | None
    assigned_to: str | None
    version: int
    terms_version: int
    risk_score: int = Field(ge=0, le=100)
    risk_factors: list[dict[str, JsonValue]]
    created_at: datetime
    updated_at: datetime
    due_at: datetime
    checklist: list[str]
    sla: str
    risk_band: str


class CasePage(BaseModel):
    items: list[LCView]
    total: int
    page: int
    page_size: int


class DocumentView(BaseModel):
    id: str
    lc_id: str
    type: str
    number: str
    version: int
    filename: str
    sha256: str
    mime: str
    size: int
    fields: dict[str, JsonValue]
    uploaded_by: str
    uploaded_at: datetime
    reason: str


class LCDetailView(LCView):
    allowed_actions: list[str]
    review_checklist: list[str]
    documents: list[DocumentView]
    validation: ValidationView | None
    discrepancies: list[dict]
    comments: list[dict]
    decisions: list[dict]
    versions: list[dict]
    audit: list[dict]
    assignee_name: str
