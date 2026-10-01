import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, select

from app import state_machine as sm
from app.clock import clock
from app.enums import (
    CourierStatus,
    LedgerAccount,
    OrderEvent,
    OrderStatus,
)
from app.ledger import account_balance, is_balanced, order_totals
from app.models import AuditLog, Order
from app.seed import seed_minimal

AMOUNT = 2800
CODE = "482913"
S = OrderStatus
E = OrderEvent


@pytest.fixture()
def db(session: Session) -> Session:
    seed_minimal(session)
    return session


def new_order(db: Session) -> Order:
    order = sm.place_order(
        db, buyer_id="B-0001", seller_id="S-0001", amount_bdt=AMOUNT,
        product_category="clothing", delivery_code=CODE,
    )  # fmt: skip
    db.commit()
    return order


def balances(db: Session, order_id: str) -> dict[str, int]:
    return {a.value: account_balance(db, order_id, a) for a in LedgerAccount}


def audit_actions(db: Session, order_id: str) -> list[str]:
    rows = db.exec(select(AuditLog).where(AuditLog.entity_id == order_id)).all()
    return [r.action for r in rows]


def drive_to(db: Session, order_id: str, status: OrderStatus) -> None:
    """Put an order into any status through legal events only."""
    if status == S.HELD:
        return
    if status in (S.DELIVERED, S.RELEASED):
        sm.apply_event(db, order_id, E.DELIVERY_CONFIRMED)
        if status == S.RELEASED:
            sm.apply_event(db, order_id, E.HOLD_EXPIRED)
        return
    if status == S.DISPUTABLE:
        sm.apply_event(db, order_id, E.COURIER_LOST)
        return
    sm.apply_event(db, order_id, E.DISPUTE_FILED)
    if status == S.REFUNDED:
        sm.apply_event(db, order_id, E.ANALYST_REFUND)
    elif status == S.ESCALATED:
        sm.apply_event(db, order_id, E.ANALYST_ESCALATE)


# ---- every legal transition, and every illegal one -------------------------------------------

LEGAL = [(frm, ev) for (frm, ev) in sm.TRANSITIONS if frm is not None]


@pytest.mark.parametrize(("start", "event"), LEGAL)
def test_every_legal_transition(db: Session, start: OrderStatus, event: OrderEvent) -> None:
    order = new_order(db)
    drive_to(db, order.id, start)
    assert db.get(Order, order.id).status == start

    result = sm.apply_event(db, order.id, event)
    db.commit()

    assert result.status == sm.TRANSITIONS[(start, event)].to
    assert is_balanced(db, order.id)
    assert f"ORDER_{event}" in audit_actions(db, order.id)


ALL_PAIRS = [(s, e) for s in OrderStatus for e in OrderEvent if e != E.PLACE_ORDER]
ILLEGAL = [(s, e) for (s, e) in ALL_PAIRS if (s, e) not in sm.TRANSITIONS]


@pytest.mark.parametrize(("start", "event"), ILLEGAL)
def test_every_illegal_transition_is_rejected(
    db: Session, start: OrderStatus, event: OrderEvent
) -> None:
    order = new_order(db)
    drive_to(db, order.id, start)
    totals_before = order_totals(db, order.id)

    with pytest.raises(sm.IllegalTransition):
        sm.apply_event(db, order.id, event)

    assert db.get(Order, order.id).status == start
    assert order_totals(db, order.id) == totals_before


def test_unknown_order_and_unknown_parties(db: Session) -> None:
    with pytest.raises(LookupError):
        sm.apply_event(db, "O-9999", E.DELIVERY_CONFIRMED)
    with pytest.raises(LookupError):
        sm.place_order(
            db, buyer_id="B-0001", seller_id="S-9999", amount_bdt=100,
            product_category="x", delivery_code=CODE,
        )  # fmt: skip
    with pytest.raises(ValueError):
        sm.place_order(
            db, buyer_id="B-0001", seller_id="S-0001", amount_bdt=0,
            product_category="x", delivery_code=CODE,
        )  # fmt: skip


# ---- ledger balances after each money scenario ------------------------------------------------


def test_placing_an_order_holds_the_money(db: Session) -> None:
    order = new_order(db)
    assert order.status == S.HELD
    assert balances(db, order.id) == {
        "BUYER_WALLET": -AMOUNT, "HOLD": AMOUNT, "SELLER_WALLET": 0, "REFUND": 0,
    }  # fmt: skip
    assert is_balanced(db, order.id)


def test_happy_path_releases_after_the_hold_period(db: Session) -> None:
    order = new_order(db)
    sm.record_courier_event(db, order.id, CourierStatus.IN_TRANSIT)
    sm.record_courier_event(db, order.id, CourierStatus.DELIVERED)
    db.commit()
    order = db.get(Order, order.id)
    assert order.status == S.DELIVERED
    assert order.hold_until == order.delivered_at + timedelta(hours=72)
    assert balances(db, order.id)["HOLD"] == AMOUNT  # still held

    assert sm.advance_clock(db, 71) == []  # one hour short
    db.commit()
    assert db.get(Order, order.id).status == S.DELIVERED

    assert sm.advance_clock(db, 1) == [(order.id, E.HOLD_EXPIRED)]
    db.commit()
    released = db.get(Order, order.id)
    assert released.status == S.RELEASED
    assert released.released_at is not None
    assert balances(db, order.id) == {
        "BUYER_WALLET": -AMOUNT, "HOLD": 0, "SELLER_WALLET": AMOUNT, "REFUND": 0,
    }  # fmt: skip
    assert is_balanced(db, order.id)


def test_refund_returns_money_to_the_buyer(db: Session) -> None:
    order = new_order(db)
    sm.apply_event(db, order.id, E.DELIVERY_CONFIRMED)
    sm.apply_event(db, order.id, E.DISPUTE_FILED, actor="buyer")
    assert balances(db, order.id)["HOLD"] == AMOUNT  # funds stay in HOLD while disputed
    sm.apply_event(db, order.id, E.ANALYST_REFUND, actor="analyst-1")
    db.commit()

    assert db.get(Order, order.id).status == S.REFUNDED
    assert balances(db, order.id) == {
        "BUYER_WALLET": 0, "HOLD": 0, "SELLER_WALLET": 0, "REFUND": 0,
    }  # fmt: skip
    assert is_balanced(db, order.id)


def test_rejected_claim_releases_to_the_seller(db: Session) -> None:
    order = new_order(db)
    sm.apply_event(db, order.id, E.DELIVERY_CONFIRMED)
    sm.apply_event(db, order.id, E.DISPUTE_FILED)
    sm.apply_event(db, order.id, E.ANALYST_REJECT)
    db.commit()

    assert db.get(Order, order.id).status == S.RELEASED
    assert balances(db, order.id)["SELLER_WALLET"] == AMOUNT
    assert is_balanced(db, order.id)


def test_courier_problem_then_refund(db: Session) -> None:
    order = new_order(db)
    sm.record_courier_event(db, order.id, CourierStatus.LOST)
    db.commit()
    assert db.get(Order, order.id).status == S.DISPUTABLE
    assert balances(db, order.id)["HOLD"] == AMOUNT  # no ledger move yet

    sm.apply_event(db, order.id, E.DISPUTE_FILED)
    sm.apply_event(db, order.id, E.ANALYST_REFUND)
    db.commit()
    assert db.get(Order, order.id).status == S.REFUNDED
    assert balances(db, order.id)["BUYER_WALLET"] == 0
    assert is_balanced(db, order.id)


def test_request_more_evidence_keeps_funds_held(db: Session) -> None:
    order = new_order(db)
    sm.apply_event(db, order.id, E.DISPUTE_FILED)
    sm.apply_event(db, order.id, E.ANALYST_REQUEST_EVIDENCE)
    assert db.get(Order, order.id).status == S.DISPUTED
    assert balances(db, order.id)["HOLD"] == AMOUNT


def test_escalated_case_can_still_be_resolved(db: Session) -> None:
    order = new_order(db)
    sm.apply_event(db, order.id, E.DISPUTE_FILED)
    sm.apply_event(db, order.id, E.APPEAL, actor="seller")
    assert db.get(Order, order.id).status == S.ESCALATED
    sm.apply_event(db, order.id, E.ANALYST_REJECT)
    assert db.get(Order, order.id).status == S.RELEASED
    assert is_balanced(db, order.id)


def test_money_cannot_move_twice(db: Session) -> None:
    order = new_order(db)
    drive_to(db, order.id, S.RELEASED)
    for event in (E.HOLD_EXPIRED, E.ANALYST_REFUND, E.ANALYST_REJECT, E.DISPUTE_FILED):
        with pytest.raises(sm.IllegalTransition):
            sm.apply_event(db, order.id, event)
    assert balances(db, order.id)["SELLER_WALLET"] == AMOUNT


# ---- delivery code, courier events, timers, audit ---------------------------------------------


def test_delivery_code(db: Session) -> None:
    order = new_order(db)
    with pytest.raises(sm.InvalidDeliveryCode):
        sm.confirm_delivery(db, order.id, "000000")
    assert db.get(Order, order.id).status == S.HELD

    sm.confirm_delivery(db, order.id, CODE)
    assert db.get(Order, order.id).status == S.DELIVERED
    assert "DELIVERY_CODE_CONFIRMED" in audit_actions(db, order.id)
    assert "DELIVERY_CODE_REJECTED" in audit_actions(db, order.id)


def test_code_after_courier_delivery_keeps_the_proof(db: Session) -> None:
    order = new_order(db)
    sm.record_courier_event(db, order.id, CourierStatus.DELIVERED)
    sm.confirm_delivery(db, order.id, CODE)
    actions = audit_actions(db, order.id)
    assert "COURIER_DELIVERED" in actions
    assert "DELIVERY_CODE_CONFIRMED" in actions
    assert db.get(Order, order.id).status == S.DELIVERED


def test_code_is_not_accepted_once_disputed(db: Session) -> None:
    order = new_order(db)
    sm.apply_event(db, order.id, E.DISPUTE_FILED)
    with pytest.raises(sm.IllegalTransition):
        sm.confirm_delivery(db, order.id, CODE)


def test_missed_dispatch_deadline_makes_the_order_disputable(db: Session) -> None:
    order = new_order(db)
    assert sm.advance_clock(db, 71) == []
    assert sm.advance_clock(db, 1) == [(order.id, E.DISPATCH_DEADLINE_MISSED)]
    db.commit()
    assert db.get(Order, order.id).status == S.DISPUTABLE


def test_dispatched_order_does_not_miss_the_deadline(db: Session) -> None:
    order = new_order(db)
    sm.record_courier_event(db, order.id, CourierStatus.IN_TRANSIT)
    assert sm.advance_clock(db, 200) == []
    assert db.get(Order, order.id).status == S.HELD


def test_clock_start_is_deterministic(db: Session) -> None:
    clock.reset()
    fixed = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    order = sm.place_order(
        db, buyer_id="B-0001", seller_id="S-0001", amount_bdt=500,
        product_category="shoes", delivery_code=CODE, now=fixed,
    )  # fmt: skip
    assert order.placed_at == fixed


def test_every_transition_is_audited(db: Session) -> None:
    order = new_order(db)
    sm.apply_event(db, order.id, E.DELIVERY_CONFIRMED, actor="courier")
    sm.apply_event(db, order.id, E.DISPUTE_FILED, actor="buyer", payload={"dispute": "D-0001"})
    rows = db.exec(select(AuditLog).where(AuditLog.entity_id == order.id)).all()
    assert [r.action for r in rows] == [
        "ORDER_PLACE_ORDER", "ORDER_DELIVERY_CONFIRMED", "ORDER_DISPUTE_FILED",
    ]  # fmt: skip
    details = json.loads(rows[-1].payload_json)
    assert details == {"dispute": "D-0001", "from": "DELIVERED", "to": "DISPUTED"}
    assert rows[-1].actor == "buyer"
