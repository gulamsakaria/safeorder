"""API schemas for accounts, the wallet, wallet orders and the admin area."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.enums import ClaimType, OrderStatus, UserRole, WalletTxKind
from app.schemas import (
    MAX_AMOUNT_BDT,
    MAX_CLAIM_CHARS,
    MAX_EVIDENCE_CHARS,
    TimelineEventOut,
    TrustCheckResponse,
)

MAX_PHONE = 20
MAX_PIN = 12
MAX_REF = 40
MAX_TRACKING = 60
MAX_NOTE = 300
MAX_IMAGE_CHARS = 600_000  # a hard ceiling; the configured limit is checked in the handler

# ---- requests --------------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    phone: str = Field(min_length=1, max_length=MAX_PHONE)
    pin: str = Field(min_length=1, max_length=MAX_PIN)


class LoginRequest(BaseModel):
    phone: str = Field(min_length=1, max_length=MAX_PHONE)
    pin: str = Field(min_length=1, max_length=MAX_PIN)


class SellerModeRequest(BaseModel):
    shop_name: str = Field(min_length=1, max_length=60)
    category: str = Field(min_length=1, max_length=40)


class ChangePinRequest(BaseModel):
    old_pin: str = Field(min_length=1, max_length=MAX_PIN)
    new_pin: str = Field(min_length=1, max_length=MAX_PIN)


class AddMoneyRequest(BaseModel):
    amount_bdt: int = Field(gt=0, le=MAX_AMOUNT_BDT)


class PayRequest(BaseModel):
    to_phone: str = Field(min_length=1, max_length=MAX_PHONE)
    amount_bdt: int = Field(gt=0, le=MAX_AMOUNT_BDT)
    order_ref: str | None = Field(default=None, max_length=MAX_REF)
    pin: str = Field(min_length=1, max_length=MAX_PIN)
    confirm_risk: bool = False


class ClaimRequest(BaseModel):
    order_no: str = Field(min_length=1, max_length=MAX_REF)


class ProofRequest(BaseModel):
    tracking_no: str = Field(min_length=1, max_length=MAX_TRACKING)
    note: str = Field(default="", max_length=MAX_NOTE)
    image: str | None = Field(default=None, max_length=MAX_IMAGE_CHARS)


class ReportRequest(BaseModel):
    claim_text: str = Field(min_length=1, max_length=MAX_CLAIM_CHARS)
    evidence_text: str = Field(default="", max_length=MAX_EVIDENCE_CHARS)
    claim_type: ClaimType | None = None


class FreezeRequest(BaseModel):
    frozen: bool


class GrantRequest(BaseModel):
    amount_bdt: int = Field(gt=0, le=5000)


class AdminDecisionRequest(BaseModel):
    decision: Literal["RELEASE_TO_SELLER", "REFUND_TO_BUYER"]
    note: str = Field(min_length=1, max_length=MAX_NOTE)


class AdminClockRequest(BaseModel):
    hours: float = Field(ge=0, le=10_000)


# ---- responses -------------------------------------------------------------------------------


class MeOut(BaseModel):
    id: str
    name: str
    phone: str
    role: UserRole
    balance_bdt: int
    held_bdt: int
    is_seller: bool
    shop_name: str | None = None
    shop_category: str | None = None
    add_money_left_bdt: int


class AuthOut(BaseModel):
    token: str
    user: MeOut


class LookupOut(BaseModel):
    phone: str
    name: str
    is_seller: bool
    shop_name: str | None = None
    is_self: bool
    trust: TrustCheckResponse | None = None
    requires_extra_confirmation: bool = False


class WalletTxOut(BaseModel):
    id: int
    kind: WalletTxKind
    amount_bdt: int
    balance_after: int
    held_after: int
    counterparty_name: str | None = None
    counterparty_phone: str | None = None
    order_id: str | None = None
    note: str | None = None
    created_at: datetime


class ProofOut(BaseModel):
    tracking_no: str | None = None
    note: str | None = None
    submitted_at: datetime | None = None
    flags: list[str]
    has_image: bool


class MyOrderOut(BaseModel):
    id: str  # "UNCLAIMED" for a seller until the order number is entered
    row_key: str
    role: Literal["BUYER", "SELLER"]
    status: OrderStatus
    amount_bdt: int
    placed_at: datetime
    order_ref: str | None = None
    claimed_at: datetime | None = None
    claim_deadline: datetime | None = None
    silence_deadline: datetime | None = None
    buyer_name: str | None = None
    buyer_phone: str | None = None
    seller_name: str | None = None
    seller_phone: str | None = None
    proof: ProofOut | None = None
    dispute_ids: list[str]
    can_accept: bool
    can_report: bool
    can_submit_proof: bool
    timeline: list[TimelineEventOut]
    server_time: str


class PayOut(BaseModel):
    kind: Literal["SENT", "HELD_PAYMENT"]
    amount_bdt: int
    to_name: str
    to_phone: str
    order: MyOrderOut | None = None
    me: MeOut


class ProofImageOut(BaseModel):
    image: str | None = None


class AdminUserOut(BaseModel):
    id: str
    name: str
    phone: str
    role: UserRole
    balance_bdt: int
    held_bdt: int
    is_seller: bool
    shop_name: str | None = None
    frozen: bool
    created_at: datetime


class AdminOrderOut(BaseModel):
    id: str
    status: OrderStatus
    amount_bdt: int
    placed_at: datetime
    buyer_name: str | None = None
    buyer_phone: str | None = None
    seller_name: str | None = None
    seller_phone: str | None = None
    order_ref: str | None = None
    claimed: bool
    proof: ProofOut | None = None
    dispute_ids: list[str]
    needs_decision: bool


class AdminOverviewOut(BaseModel):
    users: int
    sellers: int
    open_orders: int
    held_total_bdt: int
    proofs_waiting: int
    disputes_open: int
    now: str


class ClockResultOut(BaseModel):
    now: str
    fired: list[dict[str, str]]
