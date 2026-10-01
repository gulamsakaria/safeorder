from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlmodel import Session, select

from app import schemas
from app.clock import SimClock, to_iso
from app.db import next_id, reset_db, write_audit
from app.enums import AnalystDecisionType, OrderStatus, Party
from app.models import (
    AnalystDecision,
    AuditLog,
    Buyer,
    Dispute,
    Order,
    Seller,
)
from app.schemas import HIDDEN_FIELDS, BuyerPublic, SellerPublic
from app.seed import seed_minimal

T0 = datetime(2026, 10, 1, 9, 0, 0, tzinfo=UTC)


def _order(order_id: str = "O-0001") -> Order:
    return Order(
        id=order_id,
        buyer_id="B-0001",
        seller_id="S-0001",
        product_category="clothing",
        amount_bdt=2800,
        delivery_code_hash="hash",
        placed_at=T0,
    )


def test_create_and_read_back(session: Session) -> None:
    seed_minimal(session)
    session.add(_order())
    session.commit()

    order = session.get(Order, "O-0001")
    assert order is not None
    assert order.status == OrderStatus.HELD
    assert order.amount_bdt == 2800
    assert session.get(Seller, "S-0001").display_name == "Demo Seller One"
    assert session.get(Buyer, "B-0002").wallet_no == "SIM-W-B0002"


def test_reset_restores_clean_state(engine, session: Session) -> None:
    seed_minimal(session)
    session.add(_order())
    session.commit()
    session.close()

    reset_db(engine)

    with Session(engine) as fresh:
        for model in (Seller, Buyer, Order, AuditLog):
            assert fresh.exec(select(model)).all() == []


def test_hidden_fields_not_in_api_schemas() -> None:
    for name in dir(schemas):
        obj = getattr(schemas, name)
        is_schema = isinstance(obj, type) and issubclass(obj, schemas.BaseModel)
        if is_schema and obj is not schemas.BaseModel:
            assert not HIDDEN_FIELDS & set(obj.model_fields), name


def test_public_schema_drops_hidden_values(session: Session) -> None:
    seed_minimal(session)
    seller = session.get(Seller, "S-0002")
    assert seller.is_high_risk is True  # the database keeps the ground truth

    dumped = SellerPublic.model_validate(seller).model_dump()
    assert not HIDDEN_FIELDS & set(dumped)
    assert "archetype" not in BuyerPublic.model_fields


def test_foreign_keys_enforced(session: Session) -> None:
    session.add(_order())  # no seller or buyer exists
    with pytest.raises(IntegrityError):
        session.commit()


def test_audit_log_is_append_only(session: Session) -> None:
    write_audit(session, "system", "ORDER_PLACED", "order", "O-0001")
    session.commit()
    row = session.exec(select(AuditLog)).one()

    row.action = "TAMPERED"
    session.add(row)
    with pytest.raises((DBAPIError, IntegrityError)):
        session.commit()
    session.rollback()

    session.delete(session.exec(select(AuditLog)).one())
    with pytest.raises((DBAPIError, IntegrityError)):
        session.commit()
    session.rollback()


def test_analyst_note_is_required(session: Session) -> None:
    seed_minimal(session)
    session.add(_order())
    session.commit()  # no ORM relationships are declared, so flush parents before children
    session.add(
        Dispute(id="D-0001", order_id="O-0001", opened_by=Party.BUYER, claim_text="x", opened_at=T0)
    )
    session.commit()

    session.add(
        AnalystDecision(
            dispute_id="D-0001",
            analyst_id="A-1",
            decision=AnalystDecisionType.REFUND_BUYER,
            note="   ",
            created_at=T0,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_next_id(session: Session) -> None:
    seed_minimal(session)
    assert next_id(session, Order, "O") == "O-0001"
    session.add(_order("O-0007"))
    session.commit()
    assert next_id(session, Order, "O") == "O-0008"


def test_clock_advances_and_resets() -> None:
    clk = SimClock(start=T0)
    assert clk.now() == T0
    assert clk.advance(72) == T0 + timedelta(hours=72)
    clk.reset()
    assert clk.now() == T0
    with pytest.raises(ValueError):
        clk.advance(-1)


def test_clock_iso_format() -> None:
    assert to_iso(T0) == "2026-10-01T09:00:00Z"


def test_all_blueprint_tables_exist(engine) -> None:
    from sqlalchemy import inspect

    expected = {
        "seller", "buyer", "seller_daily_stats", "orders", "ledger_entry", "courier_event",
        "dispute", "evidence_item", "analysis_result", "analyst_decision", "trust_snapshot",
        "audit_log",
    }  # fmt: skip
    assert set(inspect(engine).get_table_names()) == expected
