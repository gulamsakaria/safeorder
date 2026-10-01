from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app import rules
from app import state_machine as sm
from app.api import common
from app.api.deps import get_config, get_optional_trust_model, get_session
from app.clock import clock
from app.db import write_audit
from app.enums import (
    AnalystDecisionType,
    DisputeStatus,
    OrderEvent,
    Recommendation,
    Route,
)
from app.ledger import is_balanced
from app.models import (
    AnalysisResult,
    AnalystDecision,
    Buyer,
    Dispute,
    Order,
    Seller,
)
from app.schemas import AnalystCaseOut, DecisionOut, DecisionRequest, QueueItemOut
from app.trust import service
from app.trust.model import TrustModel

router = APIRouter(prefix="/analyst", tags=["analyst"])

NOT_ANALYZED = "NOT_ANALYZED"
ROUTE_PRIORITY = {Route.HUMAN_REVIEW.value: 0, NOT_ANALYZED: 1, Route.FAST_LANE_CONFIRM.value: 2}

EVENT_FOR_DECISION = {
    AnalystDecisionType.REFUND_BUYER: OrderEvent.ANALYST_REFUND,
    AnalystDecisionType.REJECT_CLAIM: OrderEvent.ANALYST_REJECT,
    AnalystDecisionType.REQUEST_MORE_EVIDENCE: OrderEvent.ANALYST_REQUEST_EVIDENCE,
    AnalystDecisionType.ESCALATE: OrderEvent.ANALYST_ESCALATE,
}
# Which analyst decisions agree with which suggestion (a courier problem usually means a refund).
AGREES_WITH = {
    Recommendation.SUGGEST_REFUND_BUYER.value: {AnalystDecisionType.REFUND_BUYER},
    Recommendation.SUGGEST_REJECT_CLAIM.value: {AnalystDecisionType.REJECT_CLAIM},
    Recommendation.SUGGEST_COURIER_ISSUE.value: {AnalystDecisionType.REFUND_BUYER},
    Recommendation.NEEDS_MORE_EVIDENCE.value: {AnalystDecisionType.REQUEST_MORE_EVIDENCE},
}


def _latest_analysis(session: Session, dispute_id: str) -> dict[str, Any] | None:
    row = session.exec(
        select(AnalysisResult)
        .where(AnalysisResult.dispute_id == dispute_id)
        .order_by(AnalysisResult.id.desc())  # type: ignore[attr-defined]
    ).first()
    return common.stored_analysis(row.result_json) if row else None


@router.get("/queue", response_model=list[QueueItemOut])
def queue(
    route: str | None = Query(default=None, max_length=30),
    status: DisputeStatus | None = None,
    min_amount_bdt: int | None = Query(default=None, ge=0),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """Disputes waiting for a human, human-review cases first, larger amounts first."""
    disputes = session.exec(select(Dispute).where(Dispute.status != DisputeStatus.RESOLVED)).all()
    items = []
    for dispute in disputes:
        order = session.get(Order, dispute.order_id)
        analysis = _latest_analysis(session, dispute.id)
        item = {
            "dispute_id": dispute.id,
            "order_id": dispute.order_id,
            "status": dispute.status,
            "amount_bdt": order.amount_bdt if order else 0,
            "opened_at": dispute.opened_at,
            "seller_deadline": dispute.seller_deadline,
            "analyzed": analysis is not None,
            "route": analysis["route"] if analysis else None,
            "recommendation": analysis["recommendation"] if analysis else None,
            "flags": analysis["flags"] if analysis else [],
        }
        shown_route = item["route"] or NOT_ANALYZED
        if route and shown_route != route:
            continue
        if status and dispute.status != status:
            continue
        if min_amount_bdt is not None and item["amount_bdt"] < min_amount_bdt:
            continue
        items.append(item)
    items.sort(
        key=lambda i: (
            ROUTE_PRIORITY[i["route"] or NOT_ANALYZED],
            -i["amount_bdt"],
            i["opened_at"],
        )
    )
    return items


@router.get("/disputes/{dispute_id}", response_model=AnalystCaseOut)
def case_view(dispute_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    """Everything an analyst needs: what happened, why it is risky, and what to do next."""
    dispute = session.get(Dispute, dispute_id)
    if dispute is None:
        raise LookupError(f"dispute {dispute_id} not found")
    order = session.get(Order, dispute.order_id)
    assert order is not None
    buyer, seller = session.get(Buyer, order.buyer_id), session.get(Seller, order.seller_id)
    snapshot = service.latest_snapshot(session, order.seller_id)
    decisions = session.exec(
        select(AnalystDecision)
        .where(AnalystDecision.dispute_id == dispute_id)
        .order_by(AnalystDecision.id)  # type: ignore[arg-type]
    ).all()
    return {
        "dispute": common.dispute_out(session, dispute),
        "order": common.order_out(session, order),
        "buyer": buyer,
        "seller": seller,
        "seller_trust": service.snapshot_to_dict(snapshot) if snapshot else None,
        "analysis": _latest_analysis(session, dispute_id),
        "decisions": decisions,
    }


@router.post("/disputes/{dispute_id}/decision", response_model=DecisionOut)
def decide(
    dispute_id: str,
    body: DecisionRequest,
    session: Session = Depends(get_session),
    model: TrustModel | None = Depends(get_optional_trust_model),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    """Record the human decision, move the ledger, and refresh the seller's trust score."""
    dispute = session.get(Dispute, dispute_id)
    if dispute is None:
        raise LookupError(f"dispute {dispute_id} not found")
    order = session.get(Order, dispute.order_id)
    assert order is not None
    now = clock.now()
    analysis = _latest_analysis(session, dispute_id)

    sm.apply_event(
        session, order.id, EVENT_FOR_DECISION[body.decision],
        actor=f"analyst:{body.analyst_id}", now=now,
        payload={"dispute": dispute_id, "decision": body.decision.value},
    )  # fmt: skip
    session.add(
        AnalystDecision(
            dispute_id=dispute_id, analyst_id=body.analyst_id, decision=body.decision,
            note=body.note.strip(), created_at=now,
        )
    )  # fmt: skip
    if body.decision in (AnalystDecisionType.REFUND_BUYER, AnalystDecisionType.REJECT_CLAIM):
        dispute.status = DisputeStatus.RESOLVED
    elif body.decision == AnalystDecisionType.ESCALATE:
        dispute.status = DisputeStatus.ESCALATED
    else:  # more evidence: reopen and give both sides another response window
        dispute.status = DisputeStatus.OPEN
        dispute.seller_deadline = rules.seller_response_deadline(now, cfg)
    session.add(dispute)

    followed = None
    if analysis and body.decision != AnalystDecisionType.ESCALATE:
        followed = body.decision in AGREES_WITH.get(analysis["recommendation"], set())
    write_audit(
        session, f"analyst:{body.analyst_id}", "DISPUTE_DECISION", "dispute", dispute_id,
        f'{{"decision": "{body.decision.value}", "followed_suggestion": {str(followed).lower()}}}',
        now,
    )  # fmt: skip

    trust = None
    resolved = body.decision in (AnalystDecisionType.REFUND_BUYER, AnalystDecisionType.REJECT_CLAIM)
    if resolved and model is not None:
        try:
            before, after = service.apply_resolution_feedback(
                session, model, order.seller_id,
                seller_at_fault=body.decision == AnalystDecisionType.REFUND_BUYER, cfg=cfg,
            )  # fmt: skip
            trust = {
                "before": service.snapshot_to_dict(before),
                "after": service.snapshot_to_dict(after),
            }
        except service.FeaturesMissing:
            trust = None  # a decision about money must not fail because a score cannot refresh
    session.commit()
    session.refresh(order)
    return {
        "dispute_id": dispute_id,
        "decision": body.decision,
        "order_status": order.status,
        "dispute_status": dispute.status,
        "ledger_balanced": is_balanced(session, order.id),
        "followed_suggestion": followed,
        "trust": trust,
        "seller_deadline": dispute.seller_deadline,
    }
