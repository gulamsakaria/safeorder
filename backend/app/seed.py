"""Seed loader. Inserts a small, fixed, clearly synthetic data set (no real-looking identifiers).

Larger seller data sets come from scripts/generate_sellers.py (Step 3) and the demo scenarios
from scripts/seed_demo.py (Step 11).
"""

from datetime import timedelta

from sqlmodel import Session

from app.clock import clock
from app.models import Buyer, Seller

# Wallet numbers use a SIM- prefix so they can never be mistaken for a real phone number.
_SELLERS = (
    ("S-0001", "Demo Seller One", "SIM-W-S0001", "clothing", "honest_established", False, 400),
    ("S-0002", "Demo Seller Two", "SIM-W-S0002", "electronics", "fake_burst", True, 3),
)
_BUYERS = (
    ("B-0001", "Demo Buyer One", "SIM-W-B0001", 120),
    ("B-0002", "Demo Buyer Two", "SIM-W-B0002", 60),
)


def seed_minimal(session: Session) -> None:
    now = clock.now()
    for sid, name, wallet, category, archetype, high_risk, age_days in _SELLERS:
        session.add(
            Seller(
                id=sid,
                display_name=name,
                wallet_no=wallet,
                created_at=now - timedelta(days=age_days),
                category=category,
                archetype=archetype,
                is_high_risk=high_risk,
            )
        )
    for bid, name, wallet, age_days in _BUYERS:
        created = now - timedelta(days=age_days)
        session.add(Buyer(id=bid, display_name=name, wallet_no=wallet, created_at=created))
    session.commit()
