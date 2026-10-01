"""Simulated double-entry ledger. Money is whole BDT integers.

A transfer writes two entries: the source account is debited and the destination credited,
so total debits always equal total credits per order. An account's balance is credits - debits.
No real money moves anywhere; this is a sandbox.
"""

from datetime import datetime

from sqlmodel import Session, select

from app.clock import clock
from app.enums import LedgerAccount
from app.models import LedgerEntry


class LedgerError(ValueError):
    pass


def post_transfer(
    session: Session,
    order_id: str,
    source: LedgerAccount,
    destination: LedgerAccount,
    amount_bdt: int,
    reason: str,
    now: datetime | None = None,
) -> None:
    if amount_bdt <= 0:
        raise LedgerError("transfer amount must be positive")
    if source == destination:
        raise LedgerError("source and destination must differ")
    created_at = now or clock.now()
    session.add(
        LedgerEntry(
            order_id=order_id, account=source, debit=amount_bdt, credit=0,
            reason=reason, created_at=created_at,
        )
    )  # fmt: skip
    session.add(
        LedgerEntry(
            order_id=order_id, account=destination, debit=0, credit=amount_bdt,
            reason=reason, created_at=created_at,
        )
    )  # fmt: skip
    session.flush()


def _entries(session: Session, order_id: str) -> list[LedgerEntry]:
    return list(session.exec(select(LedgerEntry).where(LedgerEntry.order_id == order_id)).all())


def order_totals(session: Session, order_id: str) -> tuple[int, int]:
    """(total debits, total credits) for one order."""
    entries = _entries(session, order_id)
    return sum(e.debit for e in entries), sum(e.credit for e in entries)


def is_balanced(session: Session, order_id: str) -> bool:
    debits, credits = order_totals(session, order_id)
    return debits == credits


def account_balance(session: Session, order_id: str, account: LedgerAccount) -> int:
    entries = [e for e in _entries(session, order_id) if e.account == account]
    return sum(e.credit - e.debit for e in entries)
