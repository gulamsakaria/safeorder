"""Trust Check, trust snapshots and the feedback loop (BLUEPRINT.md Sections 7 and 9.4).

The live Trust Check reads precomputed features from the ``seller_features`` table. After an
analyst decision the seller's counters are updated and a new snapshot is stored, so the console
can show the score before and after.
"""

import json
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.clock import clock, to_iso
from app.enums import SnapshotTrigger, TrustBand
from app.models import Seller, SellerFeatures, TrustSnapshot
from app.trust.model import TrustModel, TrustResult


class FeaturesMissing(RuntimeError):
    pass


def find_seller(session: Session, seller_id: str | None, wallet_no: str | None) -> Seller:
    seller = None
    if seller_id:
        seller = session.get(Seller, seller_id)
    elif wallet_no:
        seller = session.exec(select(Seller).where(Seller.wallet_no == wallet_no)).first()
    if seller is None:
        raise LookupError("seller not found")
    return seller


def check_seller(
    session: Session,
    model: TrustModel,
    *,
    seller_id: str | None = None,
    wallet_no: str | None = None,
    cfg: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> TrustResult:
    seller = find_seller(session, seller_id, wallet_no)
    row = session.get(SellerFeatures, seller.id)
    if row is None:
        raise FeaturesMissing(f"no trust features stored for {seller.id}")
    values = {c: getattr(row, c) for c in model.feature_columns}
    return model.predict(
        values,
        seller_id=seller.id,
        order_count=row.orders_total,
        generated_at=now or clock.now(),
        cfg=cfg,
    )


def latest_snapshot(session: Session, seller_id: str) -> TrustSnapshot | None:
    return session.exec(
        select(TrustSnapshot)
        .where(TrustSnapshot.seller_id == seller_id)
        .order_by(TrustSnapshot.id.desc())  # type: ignore[attr-defined]
    ).first()


def record_snapshot(
    session: Session, result: TrustResult, trigger: SnapshotTrigger
) -> TrustSnapshot:
    assert result.seller_id is not None
    snapshot = TrustSnapshot(
        seller_id=result.seller_id,
        score=result.model_score,
        band=result.band,
        reasons_json=json.dumps([r.to_api() for r in result.reasons], ensure_ascii=False),
        model_version=result.model_version,
        trigger=trigger,
        created_at=result.generated_at,
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def ensure_initial_snapshot(
    session: Session, model: TrustModel, seller_id: str, cfg: dict[str, Any] | None = None
) -> TrustSnapshot:
    snapshot = latest_snapshot(session, seller_id)
    if snapshot is None:
        result = check_seller(session, model, seller_id=seller_id, cfg=cfg)
        snapshot = record_snapshot(session, result, SnapshotTrigger.INITIAL)
    return snapshot


def snapshot_to_dict(snapshot: TrustSnapshot) -> dict[str, Any]:
    """API view of a snapshot. The score stays hidden behind the limited-history band."""
    hidden = snapshot.band == TrustBand.LIMITED_HISTORY
    return {
        "id": snapshot.id,
        "score": None if hidden else snapshot.score,
        "band": snapshot.band.value,
        "reasons": json.loads(snapshot.reasons_json),
        "model_version": snapshot.model_version,
        "trigger": snapshot.trigger.value,
        "created_at": to_iso(snapshot.created_at),
    }


def apply_resolution_feedback(
    session: Session,
    model: TrustModel,
    seller_id: str,
    *,
    seller_at_fault: bool,
    cfg: dict[str, Any] | None = None,
) -> tuple[TrustSnapshot, TrustSnapshot]:
    """Update the seller's counters after a resolved dispute and store a new snapshot.

    The disputed order joins the seller's history. A refund to the buyer counts as a refund and a
    dispute against the seller; a rejected claim only adds a completed order. The rates are
    recomputed from the counters. Returns the snapshots before and after.
    """
    before = ensure_initial_snapshot(session, model, seller_id, cfg)
    row = session.get(SellerFeatures, seller_id)
    if row is None:
        raise FeaturesMissing(f"no trust features stored for {seller_id}")
    row.orders_total += 1
    if seller_at_fault:
        row.refund_count += 1
        row.dispute_count += 1
    row.refund_rate = row.refund_count / row.orders_total
    row.dispute_rate = row.dispute_count / row.orders_total
    session.add(row)
    session.flush()
    result = check_seller(session, model, seller_id=seller_id, cfg=cfg)
    after = record_snapshot(session, result, SnapshotTrigger.DISPUTE_RESOLVED)
    return before, after
