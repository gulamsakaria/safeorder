"""Creating accounts and seller profiles, and keeping a new seller's trust inputs up to date."""

from collections import Counter
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app import wallet
from app.api.errors import ApiError
from app.auth import hash_pin, normalize_phone, validate_pin
from app.clock import clock
from app.db import next_id, write_audit
from app.enums import OrderStatus, WalletTxKind
from app.models import Buyer, Dispute, Order, Seller, SellerFeatures, User

BURST_RATIO_FLOOR = 1.0


def create_user(
    session: Session,
    *,
    phone: str,
    name: str,
    pin: str,
    cfg: dict[str, Any],
    bonus: bool = True,
) -> User:
    phone = normalize_phone(phone)
    validate_pin(pin, cfg)
    name = " ".join(name.split())
    if not 2 <= len(name) <= 40:
        raise ApiError(422, "VALIDATION_ERROR", "the name must have 2 to 40 characters")
    if session.exec(select(User).where(User.phone == phone)).first() is not None:
        raise ApiError(409, "PHONE_TAKEN", "this phone number already has an account")
    now = clock.now()
    buyer = Buyer(
        id=next_id(session, Buyer, "B", width=6), display_name=name, wallet_no=phone, created_at=now
    )
    session.add(buyer)
    session.flush()
    user = User(
        id=next_id(session, User, "U"),
        phone=phone,
        name=name,
        pin_hash=hash_pin(pin),
        created_at=now,
        buyer_id=buyer.id,
    )
    session.add(user)
    session.flush()
    if bonus and cfg["wallet"]["signup_bonus_bdt"] > 0:
        wallet.credit(session, user, cfg["wallet"]["signup_bonus_bdt"], WalletTxKind.SIGNUP_BONUS,
                      note="sandbox welcome money", now=now)  # fmt: skip
    write_audit(session, f"user:{user.id}", "USER_REGISTERED", "user", user.id, "{}", now)
    return user


def enable_seller_mode(
    session: Session, user: User, shop_name: str, category: str, cfg: dict[str, Any]
) -> User:
    shop_name = " ".join(shop_name.split())
    if not 2 <= len(shop_name) <= 40:
        raise ApiError(422, "VALIDATION_ERROR", "the shop name must have 2 to 40 characters")
    if user.seller_id is None:
        now = clock.now()
        seller = Seller(
            id=next_id(session, Seller, "S"),
            display_name=shop_name,
            wallet_no=user.phone,
            created_at=now,
            category=category,
        )
        session.add(seller)
        session.flush()
        user.seller_id = seller.id
        session.add(SellerFeatures(seller_id=seller.id, **_features_for(session, seller, now)))
        write_audit(session, f"user:{user.id}", "SELLER_MODE_ON", "user", user.id, "{}", now)
    else:
        seller = session.get(Seller, user.seller_id)
        assert seller is not None
        seller.display_name = shop_name
        seller.category = category
        session.add(seller)
    user.shop_name = shop_name
    user.shop_category = category
    session.add(user)
    session.flush()
    return user


def _features_for(session: Session, seller: Seller, now: datetime) -> dict[str, Any]:
    """Trust inputs worked out from the seller's own orders (a brand-new seller has none)."""
    orders = session.exec(select(Order).where(Order.seller_id == seller.id)).all()
    total = len(orders)
    day, week, month = (now.timestamp() - h * 3600 for h in (24, 24 * 7, 24 * 30))

    def since(o: Order, edge: float) -> bool:
        return _aware(o.placed_at).timestamp() >= edge

    buyers_30d = Counter(o.buyer_id for o in orders if since(o, month))
    buyers_24h = {o.buyer_id for o in orders if since(o, day)}
    per_buyer = Counter(o.buyer_id for o in orders)
    disputed = {d.order_id for d in session.exec(select(Dispute)).all()} if total else set()
    refunds = sum(1 for o in orders if o.status == OrderStatus.REFUNDED)
    disputes = sum(1 for o in orders if o.id in disputed)
    unique_30d = len(buyers_30d)
    return {
        "as_of": now,
        "account_age_days": max(0.0, (now - _aware(seller.created_at)).total_seconds() / 86400),
        "orders_7d": float(sum(1 for o in orders if since(o, week))),
        "orders_30d": float(sum(1 for o in orders if since(o, month))),
        "unique_buyers_24h": float(len(buyers_24h)),
        "unique_buyers_30d": float(unique_30d),
        "buyer_burst_ratio": len(buyers_24h) / max(BURST_RATIO_FLOOR, unique_30d / 30),
        "repeat_buyer_ratio": (sum(1 for c in per_buyer.values() if c > 1) / len(per_buyer))
        if per_buyer
        else 0.0,
        "buyer_concentration": (max(per_buyer.values()) / total) if total else 0.0,
        "refund_rate": refunds / total if total else 0.0,
        "dispute_rate": disputes / total if total else 0.0,
        "median_cashout_latency_min": None,
        "ticket_vs_category_ratio": None,
        "shared_buyer_overlap": 0.0,
        "orders_total": total,
        "refund_count": refunds,
        "dispute_count": disputes,
    }


def _aware(value: datetime) -> datetime:
    from datetime import UTC

    return value if value.tzinfo else value.replace(tzinfo=UTC)


def refresh_seller_features(session: Session, seller_id: str) -> None:
    """Recompute the trust inputs of a wallet seller from their orders (not for synthetic ones)."""
    seller = session.get(Seller, seller_id)
    owner = session.exec(select(User).where(User.seller_id == seller_id)).first()
    if seller is None or owner is None:
        return
    values = _features_for(session, seller, clock.now())
    row = session.get(SellerFeatures, seller_id)
    if row is None:
        session.add(SellerFeatures(seller_id=seller_id, **values))
    else:
        for key, value in values.items():
            setattr(row, key, value)
        session.add(row)
    session.flush()
