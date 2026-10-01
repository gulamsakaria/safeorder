import pytest
from sqlmodel import Session

from app.enums import LedgerAccount
from app.ledger import LedgerError, account_balance, is_balanced, order_totals, post_transfer
from app.models import Order
from app.seed import seed_minimal
from tests.test_db import T0


@pytest.fixture()
def order(session: Session) -> Order:
    seed_minimal(session)
    row = Order(
        id="O-0001", buyer_id="B-0001", seller_id="S-0001", product_category="shoes",
        amount_bdt=1000, delivery_code_hash="h", placed_at=T0,
    )  # fmt: skip
    session.add(row)
    session.commit()
    return row


def test_transfer_writes_two_balanced_entries(session: Session, order: Order) -> None:
    post_transfer(session, order.id, LedgerAccount.BUYER_WALLET, LedgerAccount.HOLD, 1000, "T")
    assert order_totals(session, order.id) == (1000, 1000)
    assert is_balanced(session, order.id)
    assert account_balance(session, order.id, LedgerAccount.HOLD) == 1000
    assert account_balance(session, order.id, LedgerAccount.BUYER_WALLET) == -1000


@pytest.mark.parametrize("amount", [0, -5])
def test_rejects_non_positive_amount(session: Session, order: Order, amount: int) -> None:
    with pytest.raises(LedgerError):
        post_transfer(
            session, order.id, LedgerAccount.HOLD, LedgerAccount.SELLER_WALLET, amount, "x"
        )


def test_rejects_same_account(session: Session, order: Order) -> None:
    with pytest.raises(LedgerError):
        post_transfer(session, order.id, LedgerAccount.HOLD, LedgerAccount.HOLD, 10, "x")


def test_empty_ledger_is_balanced(session: Session, order: Order) -> None:
    assert order_totals(session, order.id) == (0, 0)
    assert is_balanced(session, order.id)
