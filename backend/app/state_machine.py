"""Order state machine (BLUEPRINT.md Section 6.1).

Order status changes only through ``apply_event``. Every transition moves the ledger when the
table says so and writes an audit-log row. Functions flush but never commit: the caller owns the
transaction (``db.session_scope``).
"""

import hashlib
import hmac
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app import rules
from app.clock import clock
from app.db import next_id, write_audit
from app.enums import CourierStatus, LedgerAccount, OrderEvent, OrderStatus
from app.ledger import post_transfer
from app.models import Buyer, CourierEvent, Order, Seller

Account = LedgerAccount
Status = OrderStatus
Event = OrderEvent


class IllegalTransition(Exception):
    pass


class InvalidDeliveryCode(Exception):
    pass


@dataclass(frozen=True)
class Transition:
    to: OrderStatus
    ledger: tuple[LedgerAccount, LedgerAccount] | None  # (source, destination)
    reason: str = ""


_DISPUTABLE_FROM = (Status.HELD, Status.DELIVERED, Status.DISPUTABLE)

TRANSITIONS: dict[tuple[OrderStatus | None, OrderEvent], Transition] = {
    (None, Event.PLACE_ORDER): Transition(
        Status.HELD, (Account.BUYER_WALLET, Account.HOLD), "SAFE_ORDER_HOLD"
    ),
    (Status.HELD, Event.DELIVERY_CONFIRMED): Transition(Status.DELIVERED, None),
    (Status.HELD, Event.COURIER_LOST): Transition(Status.DISPUTABLE, None),
    (Status.HELD, Event.DISPATCH_DEADLINE_MISSED): Transition(Status.DISPUTABLE, None),
    (Status.DELIVERED, Event.HOLD_EXPIRED): Transition(
        Status.RELEASED, (Account.HOLD, Account.SELLER_WALLET), "HOLD_RELEASED"
    ),
    **{
        (status, Event.DISPUTE_FILED): Transition(Status.DISPUTED, None)
        for status in _DISPUTABLE_FROM
    },
    (Status.DISPUTED, Event.ANALYST_REFUND): Transition(
        Status.REFUNDED, (Account.HOLD, Account.BUYER_WALLET), "REFUND_TO_BUYER"
    ),
    (Status.DISPUTED, Event.ANALYST_REJECT): Transition(
        Status.RELEASED, (Account.HOLD, Account.SELLER_WALLET), "CLAIM_REJECTED_RELEASE"
    ),
    (Status.DISPUTED, Event.ANALYST_REQUEST_EVIDENCE): Transition(Status.DISPUTED, None),
    (Status.DISPUTED, Event.ANALYST_ESCALATE): Transition(Status.ESCALATED, None),
    (Status.DISPUTED, Event.APPEAL): Transition(Status.ESCALATED, None),
    # Assumption (see DECISIONS.md): an escalated case is finally resolved by an analyst, otherwise
    # the held funds could never leave HOLD.
    (Status.ESCALATED, Event.ANALYST_REFUND): Transition(
        Status.REFUNDED, (Account.HOLD, Account.BUYER_WALLET), "REFUND_TO_BUYER"
    ),
    (Status.ESCALATED, Event.ANALYST_REJECT): Transition(
        Status.RELEASED, (Account.HOLD, Account.SELLER_WALLET), "CLAIM_REJECTED_RELEASE"
    ),
}


def hash_delivery_code(order_id: str, code: str) -> str:
    return hashlib.sha256(f"{order_id}:{code}".encode()).hexdigest()


def _audit(
    session: Session,
    actor: str,
    action: str,
    order_id: str,
    payload: dict[str, Any],
    now: datetime | None = None,
) -> None:
    """Audit row stamped with the same time as the event it records."""
    write_audit(session, actor, action, "order", order_id, json.dumps(payload, sort_keys=True), now)


def place_order(
    session: Session,
    *,
    buyer_id: str,
    seller_id: str,
    amount_bdt: int,
    product_category: str,
    delivery_code: str | Callable[[str], str],
    now: datetime | None = None,
    actor: str = "buyer",
) -> Order:
    """Create a Safe Order and hold the money: BUYER_WALLET -> HOLD.

    ``delivery_code`` is the code itself, or a function that derives it from the new order id.
    """
    if amount_bdt <= 0:
        raise ValueError("amount_bdt must be positive")
    if session.get(Buyer, buyer_id) is None or session.get(Seller, seller_id) is None:
        raise LookupError("unknown buyer or seller")
    now = now or clock.now()
    transition = TRANSITIONS[(None, Event.PLACE_ORDER)]
    order_id = next_id(session, Order, "O")
    order = Order(
        id=order_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        product_category=product_category,
        amount_bdt=amount_bdt,
        status=transition.to,
        delivery_code_hash=hash_delivery_code(
            order_id, delivery_code(order_id) if callable(delivery_code) else delivery_code
        ),
        placed_at=now,
    )
    session.add(order)
    session.flush()
    assert transition.ledger is not None
    post_transfer(session, order_id, *transition.ledger, amount_bdt, transition.reason, now)
    _audit(session, actor, f"ORDER_{Event.PLACE_ORDER}", order_id, {"to": transition.to}, now)
    return order


def apply_event(
    session: Session,
    order_id: str,
    event: OrderEvent,
    *,
    actor: str = "system",
    now: datetime | None = None,
    payload: dict[str, Any] | None = None,
) -> Order:
    """Apply one event to an existing order or raise ``IllegalTransition``."""
    order = session.get(Order, order_id)
    if order is None:
        raise LookupError(f"unknown order {order_id}")
    transition = TRANSITIONS.get((order.status, event))
    if transition is None:
        raise IllegalTransition(f"event {event} is not allowed in status {order.status}")
    now = now or clock.now()
    previous = order.status

    if transition.ledger is not None:
        post_transfer(
            session, order.id, *transition.ledger, order.amount_bdt, transition.reason, now
        )
    order.status = transition.to
    if event == Event.DELIVERY_CONFIRMED:
        order.delivered_at = now
        order.hold_until = rules.hold_until(now)
    if transition.to == Status.RELEASED:
        order.released_at = now
    session.add(order)
    session.flush()

    details = {"from": previous, "to": transition.to, **(payload or {})}
    _audit(session, actor, f"ORDER_{event}", order.id, details, now)
    return order


def confirm_delivery(
    session: Session, order_id: str, code: str, *, now: datetime | None = None
) -> Order:
    """Buyer confirms with the delivery code. A wrong code never changes anything."""
    order = session.get(Order, order_id)
    if order is None:
        raise LookupError(f"unknown order {order_id}")
    expected = order.delivery_code_hash
    if not hmac.compare_digest(expected, hash_delivery_code(order_id, code)):
        _audit(session, "buyer", "DELIVERY_CODE_REJECTED", order_id, {}, now)
        raise InvalidDeliveryCode("wrong delivery code")
    if order.status == Status.HELD:
        _audit(session, "buyer", "DELIVERY_CODE_CONFIRMED", order_id, {}, now)
        return apply_event(session, order_id, Event.DELIVERY_CONFIRMED, actor="buyer", now=now)
    if order.status == Status.DELIVERED:  # courier already marked it delivered; keep the proof
        _audit(session, "buyer", "DELIVERY_CODE_CONFIRMED", order_id, {}, now)
        return order
    raise IllegalTransition(f"cannot confirm delivery in status {order.status}")


def record_courier_event(
    session: Session,
    order_id: str,
    status: CourierStatus,
    *,
    now: datetime | None = None,
    source: str = "SIM",
) -> Order:
    """Store a courier status and, while the order is still HELD, apply what it implies."""
    order = session.get(Order, order_id)
    if order is None:
        raise LookupError(f"unknown order {order_id}")
    now = now or clock.now()
    session.add(CourierEvent(order_id=order_id, status=status, occurred_at=now, source=source))
    session.flush()
    _audit(session, "courier", f"COURIER_{status.value.upper()}", order_id, {"source": source}, now)
    if order.status == Status.HELD:
        if status == CourierStatus.DELIVERED:
            return apply_event(
                session, order_id, Event.DELIVERY_CONFIRMED, actor="courier", now=now
            )
        if status == CourierStatus.LOST:
            return apply_event(session, order_id, Event.COURIER_LOST, actor="courier", now=now)
    return order


def _was_dispatched(session: Session, order_id: str) -> bool:
    dispatched = (CourierStatus.IN_TRANSIT, CourierStatus.DELIVERED)
    events = session.exec(select(CourierEvent).where(CourierEvent.order_id == order_id)).all()
    return any(e.status in dispatched for e in events)


def process_timers(session: Session, now: datetime | None = None) -> list[tuple[str, OrderEvent]]:
    """Fire time-based events.

    Hold expiry releases funds; a missed dispatch deadline makes the order DISPUTABLE.
    Call after the simulated clock moves. Returns the (order_id, event) pairs that fired.
    """
    now = now or clock.now()
    fired: list[tuple[str, OrderEvent]] = []

    delivered = session.exec(select(Order).where(Order.status == Status.DELIVERED)).all()
    for order in delivered:
        if order.hold_until is not None and order.hold_until <= now:
            apply_event(session, order.id, Event.HOLD_EXPIRED, now=now)
            fired.append((order.id, Event.HOLD_EXPIRED))

    held = session.exec(select(Order).where(Order.status == Status.HELD)).all()
    for order in held:
        overdue = rules.dispatch_deadline(order.placed_at) <= now
        if overdue and not _was_dispatched(session, order.id):
            apply_event(session, order.id, Event.DISPATCH_DEADLINE_MISSED, now=now)
            fired.append((order.id, Event.DISPATCH_DEADLINE_MISSED))
    return fired


def advance_clock(session: Session, hours: float) -> list[tuple[str, OrderEvent]]:
    """Demo helper: move the simulated clock forward, then fire any timers that are now due."""
    now = clock.advance(hours)
    return process_timers(session, now)
