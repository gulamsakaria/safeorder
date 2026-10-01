"""Pydantic API schemas (BLUEPRINT.md Section 7). Hidden ground-truth fields are absent.

``Seller.archetype`` and ``Seller.is_high_risk`` exist only in the database model. A test
asserts that no schema in this module, and no response from the API, exposes them.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import load_config
from app.enums import (
    AnalystDecisionType,
    ClaimType,
    CourierStatus,
    DisputeStatus,
    LedgerAccount,
    OrderStatus,
    Party,
    SnapshotTrigger,
    TrustBand,
)

HIDDEN_FIELDS = frozenset({"archetype", "is_high_risk", "ring_id", "label_noised"})

_API = load_config()["api"]
MAX_AMOUNT_BDT = _API["max_amount_bdt"]
MAX_CLAIM_CHARS = _API["max_claim_chars"]
MAX_EVIDENCE_CHARS = _API["max_evidence_chars"]
MAX_NOTE_CHARS = _API["max_note_chars"]
MAX_ID = 40  # identifiers and wallet numbers
MAX_NAME = 80  # category and scenario names
MAX_CLOCK_HOURS = 10_000  # about 14 months of simulated time per call


# ---- requests --------------------------------------------------------------------------------


class TrustCheckRequest(BaseModel):
    seller_id: str | None = Field(default=None, max_length=MAX_ID)
    wallet_no: str | None = Field(default=None, max_length=MAX_ID)

    @model_validator(mode="after")
    def exactly_one(self) -> "TrustCheckRequest":
        if bool(self.seller_id) == bool(self.wallet_no):
            raise ValueError("give either seller_id or wallet_no")
        return self


class CreateOrderRequest(BaseModel):
    buyer_id: str = Field(min_length=1, max_length=MAX_ID)
    seller_id: str = Field(min_length=1, max_length=MAX_ID)
    amount_bdt: int = Field(gt=0, le=MAX_AMOUNT_BDT)
    product_category: str = Field(min_length=1, max_length=MAX_NAME)


class ConfirmDeliveryRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20)


class CourierEventRequest(BaseModel):
    order_id: str = Field(min_length=1, max_length=MAX_ID)
    status: CourierStatus


class AdvanceClockRequest(BaseModel):
    hours: float = Field(ge=0, le=MAX_CLOCK_HOURS)


class CreateDisputeRequest(BaseModel):
    order_id: str = Field(min_length=1, max_length=MAX_ID)
    claim_text: str = Field(min_length=1, max_length=MAX_CLAIM_CHARS)
    evidence_text: str = Field(default="", max_length=MAX_EVIDENCE_CHARS)
    claim_type: ClaimType | None = None


class SellerResponseRequest(BaseModel):
    response_text: str = Field(min_length=1, max_length=MAX_CLAIM_CHARS)
    evidence_text: str = Field(default="", max_length=MAX_EVIDENCE_CHARS)


class BuyerEvidenceRequest(BaseModel):
    evidence_text: str = Field(min_length=1, max_length=MAX_EVIDENCE_CHARS)


class DecisionRequest(BaseModel):
    decision: AnalystDecisionType
    note: str = Field(min_length=1, max_length=MAX_NOTE_CHARS)
    analyst_id: str = Field(min_length=1, max_length=MAX_ID)

    @field_validator("note")
    @classmethod
    def note_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a decision needs a written note")
        return value


class DemoResetRequest(BaseModel):
    scenario_set: str = Field(default="default", max_length=MAX_NAME)


# ---- responses -------------------------------------------------------------------------------


class SellerPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    wallet_no: str
    created_at: datetime
    category: str


class BuyerPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    wallet_no: str
    created_at: datetime


class ReasonOut(BaseModel):
    key: str
    direction: str
    text_en: str
    text_bn: str


class TrustCheckResponse(BaseModel):
    seller_id: str
    score: int | None
    band: TrustBand
    limited_history: bool
    reasons: list[ReasonOut]
    model_version: str
    generated_at: str
    requires_extra_confirmation: bool


class LedgerEntryOut(BaseModel):
    account: LedgerAccount
    debit: int
    credit: int
    reason: str
    created_at: datetime


class TimelineEventOut(BaseModel):
    t: str
    event: str


class OrderOut(BaseModel):
    id: str
    buyer_id: str
    seller_id: str
    product_category: str
    amount_bdt: int
    status: OrderStatus
    placed_at: datetime
    delivered_at: datetime | None
    hold_until: datetime | None
    released_at: datetime | None
    courier_status: CourierStatus
    ledger: list[LedgerEntryOut]
    ledger_balanced: bool
    timeline: list[TimelineEventOut]
    dispute_ids: list[str]
    can_report_problem: bool
    server_time: str
    delivery_code: str | None = Field(
        default=None, description="Sandbox only: returned once, when the order is created."
    )


class FiredEvent(BaseModel):
    order_id: str
    event: str


class ClockOut(BaseModel):
    now: str
    fired: list[FiredEvent]


class EvidenceOut(BaseModel):
    party: Party
    description_text: str
    created_at: datetime


class DisputeOut(BaseModel):
    id: str
    order_id: str
    status: DisputeStatus
    opened_by: Party
    claim_text: str
    claim_type: ClaimType | None
    opened_at: datetime
    seller_deadline: datetime | None
    seller_response_text: str | None
    seller_responded_at: datetime | None
    evidence: list[EvidenceOut]


class AnalysisOut(BaseModel):
    dispute_id: str
    order_id: str
    timeline: list[TimelineEventOut]
    class_probs: dict[str, float]
    flags: list[str]
    injection_detected: bool
    recommendation: str
    route: str
    route_reasons: list[str]
    explanation_en: str
    explanation_bn: str
    explanation_sections: dict[str, dict[str, str]]
    model_versions: dict[str, str]


class SnapshotOut(BaseModel):
    id: int
    score: int | None
    band: TrustBand
    reasons: list[ReasonOut]
    model_version: str
    trigger: SnapshotTrigger
    created_at: str


class ScoreHistoryOut(BaseModel):
    seller_id: str
    snapshots: list[SnapshotOut]


class QueueItemOut(BaseModel):
    dispute_id: str
    order_id: str
    status: DisputeStatus
    amount_bdt: int
    opened_at: datetime
    seller_deadline: datetime | None
    analyzed: bool
    route: str | None
    recommendation: str | None
    flags: list[str]


class DecisionRecordOut(BaseModel):
    analyst_id: str
    decision: AnalystDecisionType
    note: str
    created_at: datetime


class AnalystCaseOut(BaseModel):
    dispute: DisputeOut
    order: OrderOut
    buyer: BuyerPublic
    seller: SellerPublic
    seller_trust: SnapshotOut | None
    analysis: AnalysisOut | None
    decisions: list[DecisionRecordOut]


class TrustChange(BaseModel):
    before: SnapshotOut
    after: SnapshotOut


class DecisionOut(BaseModel):
    dispute_id: str
    decision: AnalystDecisionType
    order_status: OrderStatus
    dispute_status: DisputeStatus
    ledger_balanced: bool
    followed_suggestion: bool | None
    trust: TrustChange | None
    seller_deadline: datetime | None


class MetricsOut(BaseModel):
    available: bool
    summary: dict[str, Any] | None
    reports: dict[str, Any]


class DemoResetOut(BaseModel):
    scenario_set: str
    loaded: dict[str, int]
    now: str


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorOut(BaseModel):
    error: ErrorBody
