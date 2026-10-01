from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app import rules
from app import state_machine as sm
from app.analyzer.pipeline import analyze
from app.api import common
from app.api.deps import get_classifier, get_config, get_session
from app.api.errors import ApiError
from app.clock import clock
from app.db import next_id, write_audit
from app.disputes.classifier import DisputeClassifier
from app.enums import DisputeStatus, EvidenceKind, OrderEvent, Party
from app.models import Dispute, EvidenceItem, Order
from app.schemas import (
    AnalysisOut,
    BuyerEvidenceRequest,
    CreateDisputeRequest,
    DisputeOut,
    SellerResponseRequest,
)

router = APIRouter(tags=["disputes"])

OPEN_FOR_EVIDENCE = (DisputeStatus.OPEN, DisputeStatus.SELLER_RESPONDED, DisputeStatus.ANALYZED)


def _get_dispute(session: Session, dispute_id: str) -> Dispute:
    dispute = session.get(Dispute, dispute_id)
    if dispute is None:
        raise LookupError(f"dispute {dispute_id} not found")
    return dispute


def _add_evidence(session: Session, dispute_id: str, party: Party, text: str) -> None:
    if text.strip():
        session.add(
            EvidenceItem(
                dispute_id=dispute_id,
                party=party,
                description_text=text.strip(),
                kind=EvidenceKind.TEXT_DESCRIPTION,
                created_at=clock.now(),
            )
        )


@router.get("/disputes/{dispute_id}", response_model=DisputeOut)
def get_dispute(dispute_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    """The dispute as both parties see it: claim, evidence, deadline and status.

    An addition to the contract. It carries no analysis and no analyst notes; the seller screen
    needs it to show the claim and the response deadline.
    """
    return common.dispute_out(session, _get_dispute(session, dispute_id))


@router.post("/disputes", response_model=DisputeOut, status_code=201)
def create_dispute(
    body: CreateDisputeRequest,
    session: Session = Depends(get_session),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    """The buyer reports a problem. The held money stays in HOLD until an analyst decides."""
    order = session.get(Order, body.order_id)
    if order is None:
        raise LookupError(f"order {body.order_id} not found")
    now = clock.now()
    dispute_id = next_id(session, Dispute, "D")
    sm.apply_event(
        session, order.id, OrderEvent.DISPUTE_FILED, actor="buyer", now=now,
        payload={"dispute": dispute_id},
    )  # fmt: skip
    dispute = Dispute(
        id=dispute_id,
        order_id=order.id,
        opened_by=Party.BUYER,
        claim_text=body.claim_text.strip(),
        claim_type=body.claim_type.value if body.claim_type else None,
        status=DisputeStatus.OPEN,
        opened_at=now,
        seller_deadline=rules.seller_response_deadline(now, cfg),
    )
    session.add(dispute)
    session.flush()
    _add_evidence(session, dispute_id, Party.BUYER, body.evidence_text)
    write_audit(session, "buyer", "DISPUTE_OPENED", "dispute", dispute_id, "{}", now)
    session.commit()
    return common.dispute_out(session, dispute)


@router.post("/disputes/{dispute_id}/seller-response", response_model=DisputeOut)
def seller_response(
    dispute_id: str, body: SellerResponseRequest, session: Session = Depends(get_session)
) -> dict[str, Any]:
    dispute = _get_dispute(session, dispute_id)
    now = clock.now()
    if dispute.status not in (DisputeStatus.OPEN, DisputeStatus.SELLER_RESPONDED):
        raise ApiError(
            409, "ILLEGAL_STATE", f"the seller cannot respond in status {dispute.status}"
        )
    if dispute.seller_deadline is not None and now > dispute.seller_deadline:
        raise ApiError(409, "DEADLINE_PASSED", "the seller response deadline has passed")
    dispute.seller_response_text = body.response_text.strip()
    dispute.seller_responded_at = now
    dispute.status = DisputeStatus.SELLER_RESPONDED
    session.add(dispute)
    _add_evidence(session, dispute_id, Party.SELLER, body.evidence_text)
    write_audit(session, "seller", "SELLER_RESPONDED", "dispute", dispute_id, "{}", now)
    session.commit()
    return common.dispute_out(session, dispute)


@router.post("/disputes/{dispute_id}/buyer-evidence", response_model=DisputeOut)
def buyer_evidence(
    dispute_id: str, body: BuyerEvidenceRequest, session: Session = Depends(get_session)
) -> dict[str, Any]:
    """Extra evidence from the buyer, for example after an analyst asked for more.

    An addition to the contract: without it a "request more evidence" decision would give the
    buyer no way to answer.
    """
    dispute = _get_dispute(session, dispute_id)
    if dispute.status not in OPEN_FOR_EVIDENCE:
        raise ApiError(409, "ILLEGAL_STATE", f"evidence cannot be added in status {dispute.status}")
    _add_evidence(session, dispute_id, Party.BUYER, body.evidence_text)
    write_audit(session, "buyer", "BUYER_EVIDENCE_ADDED", "dispute", dispute_id, "{}", clock.now())
    session.commit()
    return common.dispute_out(session, dispute)


@router.post("/disputes/{dispute_id}/analyze", response_model=AnalysisOut)
def analyze_dispute(
    dispute_id: str,
    session: Session = Depends(get_session),
    classifier: DisputeClassifier = Depends(get_classifier),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    """Run the evidence analyzer. It only suggests; it never moves money."""
    dispute = _get_dispute(session, dispute_id)
    if dispute.status == DisputeStatus.RESOLVED:
        raise ApiError(409, "ILLEGAL_STATE", "this dispute is already resolved")
    result = analyze(session, dispute_id, classifier, cfg)
    if dispute.status in (DisputeStatus.OPEN, DisputeStatus.SELLER_RESPONDED):
        dispute.status = DisputeStatus.ANALYZED
        session.add(dispute)
    session.commit()
    return result.to_api()
