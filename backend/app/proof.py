"""Checks on the delivery proof a seller submits (tracking number and a photo of the receipt).

Plain rules, no model: they only decide whether the proof may release the money by itself after
the buyer's silence, or must wait for an admin. They never prove that a parcel arrived.
"""

import hashlib
import json
import re

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Order

MIN_TRACKING_CHARS = 6
TRACKING_PATTERN = re.compile(r"^[A-Za-z0-9\-_/]+$")

# Flag codes shown to the buyer, the seller and the admin (texts are in the website).
NO_IMAGE = "NO_IMAGE"
BAD_TRACKING_FORMAT = "BAD_TRACKING_FORMAT"
DUPLICATE_IMAGE = "DUPLICATE_IMAGE"
DUPLICATE_TRACKING = "DUPLICATE_TRACKING"
HIGH_RISK_SELLER = "HIGH_RISK_SELLER"


def image_hash(data_url: str) -> str:
    return hashlib.sha256(data_url.encode()).hexdigest()


def check_proof(
    session: Session, order: Order, tracking: str, image_digest: str | None, seller_high_risk: bool
) -> list[str]:
    flags: list[str] = []
    if not image_digest:
        flags.append(NO_IMAGE)
    if len(tracking) < MIN_TRACKING_CHARS or not TRACKING_PATTERN.match(tracking):
        flags.append(BAD_TRACKING_FORMAT)
    if image_digest and session.exec(
        select(Order.id).where(Order.id != order.id, Order.proof_image_hash == image_digest)
    ).first():
        flags.append(DUPLICATE_IMAGE)
    if session.exec(
        select(Order.id).where(
            Order.id != order.id,
            func.lower(Order.proof_tracking) == tracking.lower(),  # type: ignore[arg-type]
        )
    ).first():
        flags.append(DUPLICATE_TRACKING)
    if seller_high_risk:
        flags.append(HIGH_RISK_SELLER)
    return flags


def flags_of(order: Order) -> list[str]:
    return json.loads(order.proof_flags_json or "[]")


def proof_is_clean(order: Order) -> bool:
    return not flags_of(order)
