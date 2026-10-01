"""The facts of one dispute, gathered from the database into a plain object.

The analyzer works on ``DisputeCase`` only, so its rules can be tested without a database.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from app.config import load_config
from app.enums import CourierStatus, Party
from app.models import AuditLog, CourierEvent, Dispute, EvidenceItem, Order

NOT_DISPATCHED = CourierStatus.NOT_DISPATCHED.value
CODE_CONFIRMED_ACTION = "DELIVERY_CODE_CONFIRMED"


@dataclass
class DisputeCase:
    dispute_id: str
    order_id: str
    amount_bdt: int
    placed_at: datetime
    opened_at: datetime
    claim_text: str
    courier_events: list[tuple[str, datetime]] = field(default_factory=list)
    code_confirmed_at: datetime | None = None
    claim_type: str | None = None
    seller_response_text: str | None = None
    seller_responded_at: datetime | None = None
    seller_deadline: datetime | None = None
    buyer_evidence: list[str] = field(default_factory=list)
    seller_evidence: list[str] = field(default_factory=list)
    buyer_disputes_in_window: int = 1  # this dispute included

    @property
    def courier_status(self) -> str:
        """Latest courier status, or ``not_dispatched`` when the courier never reported."""
        return self.courier_events[-1][0] if self.courier_events else NOT_DISPATCHED

    @property
    def delivered_at(self) -> datetime | None:
        times = [t for status, t in self.courier_events if status == CourierStatus.DELIVERED]
        return times[0] if times else None

    @property
    def delivery_code_used(self) -> bool:
        return self.code_confirmed_at is not None

    @property
    def seller_responded(self) -> bool:
        return self.seller_responded_at is not None


def load_case(session: Session, dispute_id: str, cfg: dict[str, Any] | None = None) -> DisputeCase:
    config = cfg or load_config()
    dispute = session.get(Dispute, dispute_id)
    if dispute is None:
        raise LookupError(f"unknown dispute {dispute_id}")
    order = session.get(Order, dispute.order_id)
    if order is None:
        raise LookupError(f"dispute {dispute_id} points at a missing order")

    events = session.exec(
        select(CourierEvent)
        .where(CourierEvent.order_id == order.id)
        .order_by(CourierEvent.occurred_at, CourierEvent.id)  # type: ignore[arg-type]
    ).all()
    confirmed = session.exec(
        select(AuditLog.created_at)
        .where(AuditLog.entity_id == order.id, AuditLog.action == CODE_CONFIRMED_ACTION)
        .order_by(AuditLog.created_at)  # type: ignore[arg-type]
    ).first()

    evidence = session.exec(
        select(EvidenceItem)
        .where(EvidenceItem.dispute_id == dispute.id)
        .order_by(EvidenceItem.created_at, EvidenceItem.id)  # type: ignore[arg-type]
    ).all()
    window = timedelta(days=config["rules"]["routing"]["repeat_claimant_window_days"])
    count = session.exec(
        select(Dispute.id)
        .join(Order, Order.id == Dispute.order_id)  # type: ignore[arg-type]
        .where(
            Order.buyer_id == order.buyer_id,
            Dispute.opened_by == Party.BUYER,
            Dispute.opened_at <= dispute.opened_at,
            Dispute.opened_at > dispute.opened_at - window,
        )
    ).all()

    return DisputeCase(
        dispute_id=dispute.id,
        order_id=order.id,
        amount_bdt=order.amount_bdt,
        placed_at=order.placed_at,
        opened_at=dispute.opened_at,
        claim_text=dispute.claim_text,
        courier_events=[(e.status.value, e.occurred_at) for e in events],
        code_confirmed_at=confirmed,
        claim_type=dispute.claim_type,
        seller_response_text=dispute.seller_response_text,
        seller_responded_at=dispute.seller_responded_at,
        seller_deadline=dispute.seller_deadline,
        buyer_evidence=[e.description_text for e in evidence if e.party == Party.BUYER],
        seller_evidence=[e.description_text for e in evidence if e.party == Party.SELLER],
        buyer_disputes_in_window=max(1, len(count)),
    )
