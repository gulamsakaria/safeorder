"""Admin area: users, delivery-proof decisions and the demo clock. Every route needs an admin."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlmodel import Session, select

from app import auth, payments, wallet
from app import state_machine as sm
from app.api import common
from app.api.deps import get_session
from app.api.errors import ApiError
from app.clock import clock, to_iso
from app.db import write_audit
from app.enums import DisputeStatus, OrderStatus, UserRole, WalletTxKind
from app.models import Dispute, Order, User
from app.proof import flags_of
from app.wallet_schemas import (
    AdminClockRequest,
    AdminDecisionRequest,
    AdminOrderOut,
    AdminOverviewOut,
    AdminUserOut,
    ClockResultOut,
    FreezeRequest,
    GrantRequest,
    ProofImageOut,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(auth.current_admin)])

OPEN = (OrderStatus.HELD, OrderStatus.DELIVERED, OrderStatus.DISPUTABLE)


def _order_row(session: Session, order: Order) -> dict[str, Any]:
    buyer = session.exec(select(User).where(User.buyer_id == order.buyer_id)).first()
    seller = session.exec(select(User).where(User.seller_id == order.seller_id)).first()
    has_proof = order.proof_submitted_at is not None
    return {
        "id": order.id,
        "status": order.status,
        "amount_bdt": order.amount_bdt,
        "placed_at": order.placed_at,
        "buyer_name": buyer.name if buyer else None,
        "buyer_phone": buyer.phone if buyer else None,
        "seller_name": seller.shop_name or seller.name if seller else None,
        "seller_phone": seller.phone if seller else None,
        "order_ref": order.order_ref,
        "claimed": order.claimed_at is not None,
        "proof": {
            "tracking_no": order.proof_tracking,
            "note": order.proof_note,
            "submitted_at": order.proof_submitted_at,
            "flags": flags_of(order),
            "has_image": bool(order.proof_image),
        }
        if has_proof
        else None,
        "dispute_ids": common.order_out(session, order)["dispute_ids"],
        "needs_decision": has_proof and order.status in OPEN and bool(flags_of(order)),
    }


@router.get("/overview", response_model=AdminOverviewOut)
def overview(session: Session = Depends(get_session)) -> dict[str, Any]:
    wallet_orders = session.exec(select(Order).where(Order.requires_claim == True)).all()  # noqa: E712
    # money is still held while a dispute is open or escalated
    holding = (*OPEN, OrderStatus.DISPUTED, OrderStatus.ESCALATED)
    open_orders = [o for o in wallet_orders if o.status in holding]
    return {
        "users": session.exec(select(func.count()).select_from(User)).one(),
        "sellers": session.exec(
            select(func.count()).select_from(User).where(User.seller_id != None)  # noqa: E711
        ).one(),
        "open_orders": len(open_orders),
        "held_total_bdt": sum(o.amount_bdt for o in open_orders),
        "proofs_waiting": sum(1 for o in open_orders if o.proof_submitted_at is not None),
        "disputes_open": session.exec(
            select(func.count())
            .select_from(Dispute)
            .where(Dispute.status != DisputeStatus.RESOLVED)
        ).one(),
        "now": to_iso(clock.now()),
    }


@router.get("/users", response_model=list[AdminUserOut])
def users(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    rows = session.exec(select(User).order_by(User.created_at.desc())).all()  # type: ignore[attr-defined]
    return [
        {
            "id": u.id, "name": u.name, "phone": u.phone, "role": u.role,
            "balance_bdt": u.balance_bdt, "held_bdt": u.held_bdt,
            "is_seller": u.seller_id is not None, "shop_name": u.shop_name,
            "frozen": u.frozen, "created_at": u.created_at,
        }
        for u in rows
    ]  # fmt: skip


def _user(session: Session, user_id: str) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise ApiError(404, "NOT_FOUND", "user not found")
    return user


@router.post("/users/{user_id}/freeze", response_model=AdminUserOut)
def freeze(
    user_id: str,
    body: FreezeRequest,
    admin: User = Depends(auth.current_admin),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    user = _user(session, user_id)
    if user.role == UserRole.ADMIN:
        raise ApiError(409, "ILLEGAL_STATE", "an admin account cannot be frozen")
    user.frozen = body.frozen
    session.add(user)
    write_audit(session, f"admin:{admin.id}", "USER_FROZEN" if body.frozen else "USER_UNFROZEN",
                "user", user.id, "{}", clock.now())  # fmt: skip
    session.commit()
    return users_row(user)


def users_row(u: User) -> dict[str, Any]:
    return {
        "id": u.id, "name": u.name, "phone": u.phone, "role": u.role,
        "balance_bdt": u.balance_bdt, "held_bdt": u.held_bdt,
        "is_seller": u.seller_id is not None, "shop_name": u.shop_name,
        "frozen": u.frozen, "created_at": u.created_at,
    }  # fmt: skip


@router.post("/users/{user_id}/grant", response_model=AdminUserOut)
def grant(
    user_id: str,
    body: GrantRequest,
    admin: User = Depends(auth.current_admin),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Give a user extra demo money (for example after they used up their top-up limit)."""
    user = _user(session, user_id)
    wallet.credit(session, user, body.amount_bdt, WalletTxKind.ADMIN_GRANT, note="admin grant")
    write_audit(session, f"admin:{admin.id}", "USER_GRANT", "user", user.id,
                f'{{"amount": {body.amount_bdt}}}', clock.now())  # fmt: skip
    session.commit()
    return users_row(user)


@router.get("/orders", response_model=list[AdminOrderOut])
def orders(
    status: OrderStatus | None = None,
    only_open: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    query = select(Order).where(Order.requires_claim == True)  # noqa: E712
    if status:
        query = query.where(Order.status == status)
    rows = session.exec(query.order_by(Order.placed_at.desc())).all()  # type: ignore[attr-defined]
    if only_open:
        rows = [o for o in rows if o.status in OPEN]
    return [_order_row(session, o) for o in rows[:200]]


@router.get("/orders/{order_id}/proof-image", response_model=ProofImageOut)
def proof_image(order_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    order = session.get(Order, order_id.upper())
    if order is None:
        raise ApiError(404, "NOT_FOUND", "order not found")
    return {"image": order.proof_image}


@router.post("/orders/{order_id}/decision", response_model=AdminOrderOut)
def decide(
    order_id: str,
    body: AdminDecisionRequest,
    admin: User = Depends(auth.current_admin),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Release the held money to the seller, or send it back to the buyer. A note is required."""
    order = payments.admin_decide(
        session, admin, order_id, release=body.decision == "RELEASE_TO_SELLER", note=body.note
    )
    session.commit()
    return _order_row(session, order)


@router.post("/advance-clock", response_model=ClockResultOut)
def advance_clock(body: AdminClockRequest, session: Session = Depends(get_session)):
    """Demo time travel: move the simulated clock forward and fire the due timers (the seller's
    24 hours to enter the order number, the 72 hours of buyer silence)."""
    fired = sm.advance_clock(session, body.hours)
    session.commit()
    return {
        "now": to_iso(clock.now()),
        "fired": [{"order_id": oid, "event": event.value} for oid, event in fired],
    }
