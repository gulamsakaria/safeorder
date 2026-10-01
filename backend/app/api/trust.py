from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app import rules
from app.api.deps import get_config, get_session, get_trust_model
from app.models import Seller, TrustSnapshot
from app.schemas import (
    ScoreHistoryOut,
    SellerPublic,
    TrustCheckRequest,
    TrustCheckResponse,
)
from app.trust import service
from app.trust.model import TrustModel

router = APIRouter(tags=["trust"])


@router.post("/trust/check", response_model=TrustCheckResponse)
def trust_check(
    body: TrustCheckRequest,
    session: Session = Depends(get_session),
    model: TrustModel = Depends(get_trust_model),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    """Trust Check for a seller. The first check also stores the INITIAL snapshot."""
    seller = service.find_seller(session, body.seller_id, body.wallet_no)
    result = service.check_seller(session, model, seller_id=seller.id, cfg=cfg)
    service.ensure_initial_snapshot(session, model, seller.id, cfg)
    session.commit()
    return {
        **result.to_api(),
        "requires_extra_confirmation": rules.requires_extra_confirmation(result.band, cfg),
    }


@router.get("/sellers/search", response_model=list[SellerPublic])
def search_sellers(
    q: str = Query(min_length=1, max_length=40),
    session: Session = Depends(get_session),
    cfg: dict[str, Any] = Depends(get_config),
) -> list[Seller]:
    """Find sellers by name or wallet number (an addition to the contract, used by the UI)."""
    needle = f"%{q.strip()}%"
    return list(
        session.exec(
            select(Seller)
            .where((Seller.display_name.like(needle)) | (Seller.wallet_no.like(needle)))  # type: ignore[attr-defined]
            .order_by(Seller.id)
            .limit(cfg["api"]["search_limit"])
        ).all()
    )


@router.get("/sellers/{seller_id}/score-history", response_model=ScoreHistoryOut)
def score_history(seller_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    if session.get(Seller, seller_id) is None:
        raise LookupError("seller not found")
    snapshots = session.exec(
        select(TrustSnapshot).where(TrustSnapshot.seller_id == seller_id).order_by(TrustSnapshot.id)  # type: ignore[arg-type]
    ).all()
    return {"seller_id": seller_id, "snapshots": [service.snapshot_to_dict(s) for s in snapshots]}
