"""SQLModel tables (BLUEPRINT.md Section 5).

Conventions: money is stored as whole BDT integers (no float rounding in the ledger);
datetimes are timezone-aware UTC; main entities have string ids (S-0001, O-0001, D-0001) and
append-only log tables have integer ids. No ORM relationships are declared (foreign keys only),
so commit or flush a parent row before inserting rows that reference it.

``Seller.archetype`` and ``Seller.is_high_risk`` are hidden ground truth for evaluation.
They must never appear in an API schema (see schemas.py).
"""

import datetime as dt
from datetime import datetime

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel

from app.enums import (
    AnalystDecisionType,
    CourierStatus,
    DisputeStatus,
    EvidenceKind,
    LedgerAccount,
    OrderStatus,
    Party,
    SnapshotTrigger,
    TrustBand,
)


class Seller(SQLModel, table=True):
    __tablename__ = "seller"

    id: str = Field(primary_key=True)
    display_name: str
    wallet_no: str = Field(unique=True, index=True)
    created_at: datetime
    category: str
    archetype: str | None = None  # hidden ground truth, never shown in the UI
    is_high_risk: bool = False  # hidden ground-truth label for evaluation


class Buyer(SQLModel, table=True):
    __tablename__ = "buyer"

    id: str = Field(primary_key=True)
    display_name: str
    wallet_no: str = Field(unique=True, index=True)
    created_at: datetime


class SellerDailyStats(SQLModel, table=True):
    __tablename__ = "seller_daily_stats"

    seller_id: str = Field(foreign_key="seller.id", primary_key=True)
    date: dt.date = Field(primary_key=True)
    orders: int = 0
    unique_buyers: int = 0
    inflow_bdt: int = 0
    cashout_bdt: int = 0
    refunds: int = 0
    disputes: int = 0


class Order(SQLModel, table=True):
    __tablename__ = "orders"

    id: str = Field(primary_key=True)
    buyer_id: str = Field(foreign_key="buyer.id", index=True)
    seller_id: str = Field(foreign_key="seller.id", index=True)
    product_category: str
    amount_bdt: int = Field(gt=0)
    status: OrderStatus = OrderStatus.HELD
    delivery_code_hash: str
    placed_at: datetime
    delivered_at: datetime | None = None
    hold_until: datetime | None = None
    released_at: datetime | None = None


class LedgerEntry(SQLModel, table=True):
    __tablename__ = "ledger_entry"

    id: int | None = Field(default=None, primary_key=True)
    order_id: str = Field(foreign_key="orders.id", index=True)
    account: LedgerAccount
    debit: int = 0
    credit: int = 0
    reason: str
    created_at: datetime


class CourierEvent(SQLModel, table=True):
    __tablename__ = "courier_event"

    id: int | None = Field(default=None, primary_key=True)
    order_id: str = Field(foreign_key="orders.id", index=True)
    status: CourierStatus
    occurred_at: datetime
    source: str = "SIM"


class Dispute(SQLModel, table=True):
    __tablename__ = "dispute"

    id: str = Field(primary_key=True)
    order_id: str = Field(foreign_key="orders.id", index=True)
    opened_by: Party
    claim_text: str
    status: DisputeStatus = DisputeStatus.OPEN
    opened_at: datetime
    seller_deadline: datetime | None = None
    appeal_of: str | None = Field(default=None, foreign_key="dispute.id")


class EvidenceItem(SQLModel, table=True):
    __tablename__ = "evidence_item"

    id: int | None = Field(default=None, primary_key=True)
    dispute_id: str = Field(foreign_key="dispute.id", index=True)
    party: Party
    description_text: str
    kind: EvidenceKind = EvidenceKind.TEXT_DESCRIPTION
    file_hash: str | None = None  # P2 only
    created_at: datetime


class AnalysisResult(SQLModel, table=True):
    __tablename__ = "analysis_result"

    id: int | None = Field(default=None, primary_key=True)
    dispute_id: str = Field(foreign_key="dispute.id", index=True)
    result_json: str
    model_versions_json: str
    created_at: datetime


class AnalystDecision(SQLModel, table=True):
    __tablename__ = "analyst_decision"
    __table_args__ = (CheckConstraint("length(trim(note)) > 0", name="note_required"),)

    id: int | None = Field(default=None, primary_key=True)
    dispute_id: str = Field(foreign_key="dispute.id", index=True)
    analyst_id: str
    decision: AnalystDecisionType
    note: str  # required: the check constraint rejects an empty note
    created_at: datetime


class TrustSnapshot(SQLModel, table=True):
    __tablename__ = "trust_snapshot"

    id: int | None = Field(default=None, primary_key=True)
    seller_id: str = Field(foreign_key="seller.id", index=True)
    score: int
    band: TrustBand
    reasons_json: str
    model_version: str
    trigger: SnapshotTrigger
    created_at: datetime


class AuditLog(SQLModel, table=True):
    """Append-only: database triggers (db.py) reject UPDATE and DELETE."""

    __tablename__ = "audit_log"

    id: int | None = Field(default=None, primary_key=True)
    actor: str
    action: str
    entity: str
    entity_id: str
    payload_json: str = "{}"
    created_at: datetime


class SellerFeatures(SQLModel, table=True):
    """Precomputed trust features per seller (an addition to the Section 5 tables).

    The simulated orders live in CSV files, not in the database, so the live Trust Check reads
    its inputs from here. ``refund_count`` and ``dispute_count`` let the feedback loop update the
    rates after an analyst decision without the order history.
    """

    __tablename__ = "seller_features"

    seller_id: str = Field(foreign_key="seller.id", primary_key=True)
    as_of: datetime
    account_age_days: float
    orders_7d: float
    orders_30d: float
    unique_buyers_24h: float
    unique_buyers_30d: float
    buyer_burst_ratio: float
    repeat_buyer_ratio: float
    buyer_concentration: float
    refund_rate: float
    dispute_rate: float
    median_cashout_latency_min: float | None = None
    ticket_vs_category_ratio: float | None = None
    shared_buyer_overlap: float
    orders_total: int
    refund_count: int
    dispute_count: int
