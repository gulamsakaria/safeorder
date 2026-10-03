"""Sandbox wallet balances (demo money only) and their link to the order ledger.

Every change of a balance writes a ``WalletTx`` row in the same transaction, so the history always
explains the balance. The order state machine calls ``on_ledger_move`` whenever it moves money
between BUYER_WALLET, HOLD and SELLER_WALLET; accounts that do not exist (the synthetic sellers
and buyers of the classic demo) are simply skipped.
"""

from datetime import datetime

from sqlmodel import Session, select

from app.clock import clock
from app.enums import LedgerAccount, WalletTxKind
from app.models import Order, User, WalletTx


class InsufficientFunds(ValueError):
    pass


def user_for_buyer(session: Session, buyer_id: str) -> User | None:
    return session.exec(select(User).where(User.buyer_id == buyer_id)).first()


def user_for_seller(session: Session, seller_id: str) -> User | None:
    return session.exec(select(User).where(User.seller_id == seller_id)).first()


def record(
    session: Session,
    user: User,
    kind: WalletTxKind,
    amount_bdt: int,
    *,
    counterparty: User | None = None,
    order_id: str | None = None,
    note: str | None = None,
    now: datetime | None = None,
) -> WalletTx:
    """Write one history line from the user's current balances (call after changing them)."""
    tx = WalletTx(
        user_id=user.id,
        kind=kind,
        amount_bdt=amount_bdt,
        balance_after=user.balance_bdt,
        held_after=user.held_bdt,
        counterparty_name=counterparty.name if counterparty else None,
        counterparty_phone=counterparty.phone if counterparty else None,
        order_id=order_id,
        note=note,
        created_at=now or clock.now(),
    )
    session.add(user)
    session.add(tx)
    session.flush()
    return tx


def credit(session: Session, user: User, amount: int, kind: WalletTxKind, **kwargs) -> WalletTx:
    user.balance_bdt += amount
    return record(session, user, kind, amount, **kwargs)


def debit(session: Session, user: User, amount: int, kind: WalletTxKind, **kwargs) -> WalletTx:
    if user.balance_bdt < amount:
        raise InsufficientFunds("not enough balance")
    user.balance_bdt -= amount
    return record(session, user, kind, -amount, **kwargs)


def on_ledger_move(
    session: Session,
    order: Order,
    source: LedgerAccount,
    destination: LedgerAccount,
    amount_bdt: int,
    now: datetime | None = None,
) -> None:
    """Mirror one order-ledger transfer in the wallets of the people involved, if they have any."""
    buyer = user_for_buyer(session, order.buyer_id)
    seller = user_for_seller(session, order.seller_id)
    move = (source, destination)

    if move == (LedgerAccount.BUYER_WALLET, LedgerAccount.HOLD):
        if buyer is not None:
            debit(session, buyer, amount_bdt, WalletTxKind.PAYMENT_HELD,
                  counterparty=seller, order_id=order.id, now=now)  # fmt: skip
        if seller is not None:
            seller.held_bdt += amount_bdt
            record(session, seller, WalletTxKind.PAYMENT_RECEIVED_HELD, amount_bdt,
                   counterparty=buyer, order_id=order.id, now=now)  # fmt: skip
    elif move == (LedgerAccount.HOLD, LedgerAccount.SELLER_WALLET):
        if seller is not None:
            seller.held_bdt -= amount_bdt
            seller.balance_bdt += amount_bdt
            record(session, seller, WalletTxKind.RELEASED, amount_bdt,
                   counterparty=buyer, order_id=order.id, now=now)  # fmt: skip
    elif move == (LedgerAccount.HOLD, LedgerAccount.BUYER_WALLET):
        if seller is not None:
            seller.held_bdt -= amount_bdt
            record(session, seller, WalletTxKind.REFUND_OUT, -amount_bdt,
                   counterparty=buyer, order_id=order.id, now=now)  # fmt: skip
        if buyer is not None:
            credit(session, buyer, amount_bdt, WalletTxKind.REFUNDED,
                   counterparty=seller, order_id=order.id, now=now)  # fmt: skip


def history(session: Session, user: User, limit: int = 100) -> list[WalletTx]:
    return list(
        session.exec(
            select(WalletTx)
            .where(WalletTx.user_id == user.id)
            .order_by(WalletTx.id.desc())  # type: ignore[attr-defined]
            .limit(limit)
        ).all()
    )
