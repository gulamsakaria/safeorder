"""Wallet payments: send money, held payments for sellers, claiming an order, delivery proof.

The money rules live in the order state machine and ``wallet.py``; this module checks who may do
what and calls them. Functions flush but do not commit: the API handler owns the transaction.
"""

import hashlib
import json
import secrets
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app import rules, wallet
from app import state_machine as sm
from app.api import common
from app.api.errors import ApiError
from app.clock import clock, to_iso
from app.db import write_audit
from app.enums import OrderEvent, OrderStatus, UserRole, WalletTxKind
from app.models import Order, Seller, SellerFeatures, User
from app.proof import check_proof, flags_of, image_hash
from app.trust import service as trust_service
from app.trust.model import TrustModel

CLAIMABLE = (OrderStatus.HELD,)
OPEN_STATUSES = (OrderStatus.HELD, OrderStatus.DELIVERED, OrderStatus.DISPUTABLE)
UNCLAIMED = "UNCLAIMED"
# Opaque list keys for a seller's unclaimed rows: salted, so they cannot reveal order numbers.
_ROW_SALT = secrets.token_hex(16)


def mask_phone(phone: str) -> str:
    return f"{phone[:3]}****{phone[-3:]}"


def seller_is_high_risk(
    session: Session, model: TrustModel | None, seller_id: str, cfg: dict[str, Any]
) -> bool:
    if model is None or session.get(SellerFeatures, seller_id) is None:
        return False
    try:
        result = trust_service.check_seller(session, model, seller_id=seller_id, cfg=cfg)
    except Exception:  # a failed score must never block a payment or a proof
        return False
    return result.band == "HIGH_RISK"


def add_money(session: Session, user: User, amount: int, cfg: dict[str, Any]) -> None:
    limits = cfg["wallet"]
    if amount > limits["add_money_max_bdt"]:
        raise ApiError(
            422, "VALIDATION_ERROR", f"at most {limits['add_money_max_bdt']} BDT at a time"
        )
    if user.added_total_bdt + amount > limits["add_money_total_cap_bdt"]:
        raise ApiError(409, "ADD_MONEY_LIMIT", "the demo money limit for this account is reached")
    user.added_total_bdt += amount
    wallet.credit(session, user, amount, WalletTxKind.ADD_MONEY, note="sandbox top-up")


def pay(
    session: Session,
    sender: User,
    *,
    to_phone: str,
    amount: int,
    order_ref: str | None,
    model: TrustModel | None,
    confirm_risk: bool,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """Send money. To a seller account it becomes a held payment (a Safe Order); to anyone else
    it arrives at once."""
    recipient = session.exec(select(User).where(User.phone == to_phone)).first()
    if recipient is None:
        raise ApiError(404, "NOT_FOUND", "no account has this phone number")
    if recipient.id == sender.id:
        raise ApiError(422, "VALIDATION_ERROR", "you cannot pay yourself")
    if recipient.frozen:
        raise ApiError(409, "RECIPIENT_FROZEN", "this account cannot receive money now")
    if sender.balance_bdt < amount:
        raise ApiError(409, "INSUFFICIENT_FUNDS", "not enough balance")

    if recipient.seller_id is None:
        wallet.debit(session, sender, amount, WalletTxKind.SEND_MONEY_OUT, counterparty=recipient)
        wallet.credit(session, recipient, amount, WalletTxKind.SEND_MONEY_IN, counterparty=sender)
        write_audit(session, f"user:{sender.id}", "SEND_MONEY", "user", sender.id,
                    json.dumps({"to": recipient.id, "amount": amount}), clock.now())  # fmt: skip
        return {"kind": "SENT", "order": None, "to": recipient}

    if seller_is_high_risk(session, model, recipient.seller_id, cfg) and not confirm_risk:
        raise ApiError(409, "RISK_CONFIRMATION_REQUIRED", "this seller looks high risk")
    assert sender.buyer_id is not None
    order = sm.place_order(
        session,
        buyer_id=sender.buyer_id,
        seller_id=recipient.seller_id,
        amount_bdt=amount,
        product_category=recipient.shop_category or "other",
        delivery_code=lambda order_id: common.delivery_code_for(order_id, cfg),
        requires_claim=True,
        order_ref=(order_ref or "").strip() or None,
        actor=f"user:{sender.id}",
    )
    return {"kind": "HELD_PAYMENT", "order": order, "to": recipient}


def _participant_orders(session: Session, user: User, role: str) -> list[Order]:
    column = Order.buyer_id if role == "BUYER" else Order.seller_id
    key = user.buyer_id if role == "BUYER" else user.seller_id
    if key is None:
        return []
    return list(
        session.exec(
            select(Order)
            .where(column == key, Order.requires_claim == True)  # noqa: E712
            .order_by(Order.placed_at.desc())  # type: ignore[attr-defined]
        ).all()
    )


def my_orders(session: Session, user: User, role: str) -> list[Order]:
    return _participant_orders(session, user, role)


def role_in(order: Order, user: User) -> str | None:
    if user.buyer_id == order.buyer_id:
        return "BUYER"
    if user.seller_id is not None and user.seller_id == order.seller_id:
        return "SELLER"
    return None


def load_order_for(session: Session, user: User, order_id: str) -> tuple[Order, str]:
    order = session.get(Order, order_id.strip().upper())
    role = role_in(order, user) if order is not None else None
    if order is None or role is None:
        raise ApiError(404, "NOT_FOUND", "order not found")
    return order, role


def guard_order(
    order: Order | None, user: User | None, roles: tuple[str, ...], *, admin_ok: bool = True
) -> None:
    """Wallet orders belong to two people: only they (and an admin) may touch the order and its
    dispute. Orders of the classic demo have no accounts and stay open, as before."""
    if order is None or not order.requires_claim:
        return
    if user is None:
        raise ApiError(401, "NOT_SIGNED_IN", "please sign in")
    if admin_ok and user.role == UserRole.ADMIN:
        return
    if role_in(order, user) not in roles:
        raise ApiError(403, "FORBIDDEN", "this is not your order")


def order_view(session: Session, order: Order, role: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """An order as its buyer or seller sees it (a seller sees no order number before claiming)."""
    buyer = session.exec(select(User).where(User.buyer_id == order.buyer_id)).first()
    seller = session.exec(select(User).where(User.seller_id == order.seller_id)).first()
    seller_row = session.get(Seller, order.seller_id)
    hidden = role == "SELLER" and order.claimed_at is None
    disputes = common.order_out(session, order)["dispute_ids"]
    has_proof = order.proof_submitted_at is not None
    open_now = order.status in OPEN_STATUSES
    return {
        "id": UNCLAIMED if hidden else order.id,
        "row_key": hashlib.sha256(f"{_ROW_SALT}:{order.id}".encode()).hexdigest()[:12],
        "role": role,
        "status": order.status,
        "amount_bdt": order.amount_bdt,
        "placed_at": order.placed_at,
        "order_ref": None if hidden else order.order_ref,
        "claimed_at": order.claimed_at,
        "claim_deadline": rules.claim_deadline(order.placed_at, cfg)
        if order.claimed_at is None and order.status == OrderStatus.HELD
        else None,
        "silence_deadline": rules.silence_deadline(order.proof_submitted_at, cfg)
        if has_proof and open_now
        else None,
        "buyer_name": buyer.name if buyer else None,
        "buyer_phone": (buyer.phone if role == "BUYER" else mask_phone(buyer.phone))
        if buyer
        else None,
        "seller_name": (seller_row.display_name if seller_row else None),
        "seller_phone": seller.phone if seller else None,
        "proof": {
            "tracking_no": order.proof_tracking,
            "note": order.proof_note,
            "submitted_at": order.proof_submitted_at,
            "flags": flags_of(order),
            "has_image": bool(order.proof_image),
        }
        if has_proof
        else None,
        "dispute_ids": [] if hidden else disputes,
        "can_accept": role == "BUYER" and open_now,
        "can_report": role == "BUYER" and rules.can_file_dispute(order.status),
        "can_submit_proof": role == "SELLER"
        and not hidden
        and order.status in OPEN_STATUSES
        and order.status != OrderStatus.DISPUTED,
        "timeline": [] if hidden else common.order_timeline(session, order.id),
        "server_time": to_iso(clock.now()),
    }


def claim_order(session: Session, seller_user: User, order_no: str) -> Order:
    wanted = order_no.strip()
    if not wanted:
        raise ApiError(422, "VALIDATION_ERROR", "type the order number")
    assert seller_user.seller_id is not None
    candidates = session.exec(
        select(Order)
        .where(
            Order.seller_id == seller_user.seller_id,
            Order.requires_claim == True,  # noqa: E712
            Order.claimed_at == None,  # noqa: E711
            Order.status == OrderStatus.HELD,
        )
        .order_by(Order.placed_at)  # type: ignore[arg-type]
    ).all()
    match = next(
        (
            o
            for o in candidates
            if wanted.upper() == o.id.upper() or wanted.lower() == (o.order_ref or "").lower()
        ),
        None,
    )
    if match is None:
        raise ApiError(404, "NOT_FOUND", "no waiting payment has this order number")
    now = clock.now()
    match.claimed_at = now
    session.add(match)
    write_audit(session, f"user:{seller_user.id}", "ORDER_CLAIMED", "order", match.id, "{}", now)
    session.flush()
    return match


def buyer_accept(session: Session, buyer: User, order_id: str) -> Order:
    order, role = load_order_for(session, buyer, order_id)
    if role != "BUYER":
        raise ApiError(403, "FORBIDDEN", "only the buyer can confirm delivery")
    if order.claimed_at is None:
        order.claimed_at = clock.now()
    return sm.apply_event(
        session, order.id, OrderEvent.BUYER_ACCEPTED, actor=f"user:{buyer.id}"
    )


def submit_proof(
    session: Session,
    seller_user: User,
    order_id: str,
    *,
    tracking_no: str,
    note: str,
    image: str | None,
    model: TrustModel | None,
    cfg: dict[str, Any],
) -> Order:
    order, role = load_order_for(session, seller_user, order_id)
    if role != "SELLER":
        raise ApiError(403, "FORBIDDEN", "only the seller can submit proof")
    if order.claimed_at is None:
        raise ApiError(409, "NOT_CLAIMED", "enter the order number first")
    if order.status not in OPEN_STATUSES:
        raise ApiError(409, "ILLEGAL_STATE", f"proof cannot be added in status {order.status}")
    limit = cfg["wallet"]["proof_image_max_chars"]
    if image is not None and (len(image) > limit or not image.startswith("data:image/")):
        raise ApiError(422, "VALIDATION_ERROR", "the photo is too large or not an image")
    tracking = tracking_no.strip()
    digest = image_hash(image) if image else None
    flags = check_proof(
        session, order, tracking, digest, seller_is_high_risk(session, model, order.seller_id, cfg)
    )
    now = clock.now()
    order.proof_tracking = tracking
    order.proof_note = note.strip() or None
    order.proof_image = image
    order.proof_image_hash = digest
    order.proof_submitted_at = now
    order.proof_flags_json = json.dumps(flags)
    session.add(order)
    write_audit(session, f"user:{seller_user.id}", "ORDER_PROOF_SUBMITTED", "order", order.id,
                json.dumps({"flags": flags}), now)  # fmt: skip
    session.flush()
    return order


def admin_decide(
    session: Session, admin: User, order_id: str, *, release: bool, note: str
) -> Order:
    order = session.get(Order, order_id.strip().upper())
    if order is None or not order.requires_claim:
        raise ApiError(404, "NOT_FOUND", "order not found")
    event = OrderEvent.PROOF_RELEASE if release else OrderEvent.ADMIN_REFUND
    return sm.apply_event(
        session, order.id, event, actor=f"admin:{admin.id}", payload={"note": note.strip()}
    )


def check_time(value: datetime | None) -> str | None:
    return to_iso(value) if value else None
