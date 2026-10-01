"""Builders that turn database rows into API responses (never exposing hidden fields)."""

import json
import random
from typing import Any

from sqlmodel import Session, select

from app import rules
from app.clock import clock, to_iso
from app.config import load_config
from app.enums import CourierStatus
from app.ledger import is_balanced
from app.models import AuditLog, CourierEvent, Dispute, EvidenceItem, LedgerEntry, Order

DELIVERY_CODE_SALT = "delivery-code"

# Audit-log action -> event name shown to the buyer and the analyst.
EVENT_NAMES = {
    "ORDER_PLACE_ORDER": "ORDER_PLACED_AND_HELD",
    "ORDER_DELIVERY_CONFIRMED": "DELIVERED",
    "ORDER_HOLD_EXPIRED": "HOLD_ENDED_FUNDS_RELEASED",
    "ORDER_DISPATCH_DEADLINE_MISSED": "DISPATCH_DEADLINE_MISSED",
    "ORDER_COURIER_LOST": "MARKED_DISPUTABLE_PARCEL_LOST",
    "ORDER_DISPUTE_FILED": "DISPUTE_FILED",
    "ORDER_ANALYST_REFUND": "REFUNDED_TO_BUYER",
    "ORDER_ANALYST_REJECT": "FUNDS_RELEASED_TO_SELLER",
    "ORDER_ANALYST_REQUEST_EVIDENCE": "MORE_EVIDENCE_REQUESTED",
    "ORDER_ANALYST_ESCALATE": "ESCALATED",
    "ORDER_APPEAL": "APPEAL_FILED",
}


def delivery_code_for(order_id: str, cfg: dict[str, Any] | None = None) -> str:
    """Sandbox delivery code, derived from the project seed so demo runs repeat exactly."""
    config = cfg or load_config()
    digits = config["api"]["delivery_code_digits"]
    rng = random.Random(f"{config['project']['seed']}:{DELIVERY_CODE_SALT}:{order_id}")
    return f"{rng.randrange(10**digits):0{digits}d}"


def courier_status_of(session: Session, order_id: str) -> CourierStatus:
    last = session.exec(
        select(CourierEvent)
        .where(CourierEvent.order_id == order_id)
        .order_by(CourierEvent.occurred_at.desc(), CourierEvent.id.desc())  # type: ignore[attr-defined]
    ).first()
    return last.status if last else CourierStatus.NOT_DISPATCHED


def order_timeline(session: Session, order_id: str) -> list[dict[str, str]]:
    rows = session.exec(
        select(AuditLog)
        .where(AuditLog.entity == "order", AuditLog.entity_id == order_id)
        .order_by(AuditLog.created_at, AuditLog.id)  # type: ignore[arg-type]
    ).all()
    return [{"t": to_iso(r.created_at), "event": EVENT_NAMES.get(r.action, r.action)} for r in rows]


def order_out(session: Session, order: Order, delivery_code: str | None = None) -> dict[str, Any]:
    ledger = session.exec(
        select(LedgerEntry).where(LedgerEntry.order_id == order.id).order_by(LedgerEntry.id)  # type: ignore[arg-type]
    ).all()
    dispute_ids = session.exec(select(Dispute.id).where(Dispute.order_id == order.id)).all()
    return {
        "id": order.id,
        "buyer_id": order.buyer_id,
        "seller_id": order.seller_id,
        "product_category": order.product_category,
        "amount_bdt": order.amount_bdt,
        "status": order.status,
        "placed_at": order.placed_at,
        "delivered_at": order.delivered_at,
        "hold_until": order.hold_until,
        "released_at": order.released_at,
        "courier_status": courier_status_of(session, order.id),
        "ledger": [
            {
                "account": e.account,
                "debit": e.debit,
                "credit": e.credit,
                "reason": e.reason,
                "created_at": e.created_at,
            }
            for e in ledger
        ],  # fmt: skip
        "ledger_balanced": is_balanced(session, order.id),
        "timeline": order_timeline(session, order.id),
        "dispute_ids": list(dispute_ids),
        "can_report_problem": rules.can_file_dispute(order.status),
        "server_time": to_iso(clock.now()),
        "delivery_code": delivery_code,
    }


def dispute_out(session: Session, dispute: Dispute) -> dict[str, Any]:
    evidence = session.exec(
        select(EvidenceItem)
        .where(EvidenceItem.dispute_id == dispute.id)
        .order_by(EvidenceItem.created_at, EvidenceItem.id)  # type: ignore[arg-type]
    ).all()
    return {
        "id": dispute.id,
        "order_id": dispute.order_id,
        "status": dispute.status,
        "opened_by": dispute.opened_by,
        "claim_text": dispute.claim_text,
        "claim_type": dispute.claim_type,
        "opened_at": dispute.opened_at,
        "seller_deadline": dispute.seller_deadline,
        "seller_response_text": dispute.seller_response_text,
        "seller_responded_at": dispute.seller_responded_at,
        "evidence": [
            {"party": e.party, "description_text": e.description_text, "created_at": e.created_at}
            for e in evidence
        ],
    }


ANALYSIS_KEYS = (
    "dispute_id", "order_id", "timeline", "class_probs", "flags", "injection_detected",
    "recommendation", "route", "route_reasons", "explanation_en", "explanation_bn",
    "explanation_sections", "model_versions",
)  # fmt: skip


def stored_analysis(result_json: str) -> dict[str, Any]:
    """The public part of a stored analysis (internal detail fields are left out)."""
    stored = json.loads(result_json)
    return {key: stored[key] for key in ANALYSIS_KEYS}
