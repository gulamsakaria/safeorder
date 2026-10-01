"""Seed loader. Inserts a small, fixed, clearly synthetic data set (no real-looking identifiers).

Larger seller data sets come from scripts/generate_sellers.py (Step 3) and the demo scenarios
from scripts/seed_demo.py (Step 11).
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import Engine, insert
from sqlmodel import Session

from app.clock import clock
from app.config import load_config
from app.db import create_db, reset_db
from app.models import Buyer, Seller, SellerDailyStats, SellerFeatures

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_SETS = ("empty", "default", "demo")
INSERT_CHUNK = 20_000

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


class SyntheticDataMissing(RuntimeError):
    pass


def _aware(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def load_synthetic(
    engine: Engine,
    sellers: pd.DataFrame,
    buyers: pd.DataFrame,
    daily_stats: pd.DataFrame,
    features: pd.DataFrame | None,
    as_of: str,
) -> None:
    """Insert generated sellers, buyers, daily stats and (optionally) trust features."""
    with Session(engine) as session:
        session.add_all(
            Seller(
                id=r.id, display_name=r.display_name, wallet_no=r.wallet_no,
                created_at=_aware(r.created_at), category=r.category, archetype=r.archetype,
                is_high_risk=bool(r.is_high_risk),
            )
            for r in sellers.itertuples()
        )  # fmt: skip
        session.add_all(
            Buyer(id=r.id, display_name=r.display_name, wallet_no=r.wallet_no,
                  created_at=_aware(r.created_at))
            for r in buyers.itertuples()
        )  # fmt: skip
        session.commit()
        stats = daily_stats.assign(date=lambda f: pd.to_datetime(f["date"]).dt.date)
        records = stats.to_dict(orient="records")
        for start in range(0, len(records), INSERT_CHUNK):
            session.execute(insert(SellerDailyStats), records[start : start + INSERT_CHUNK])
        session.commit()
        if features is not None:
            rows = features.reset_index().rename(columns={"index": "seller_id"})
            rows = rows.astype(object).where(rows.notna(), None)
            moment = _aware(as_of)
            session.add_all(SellerFeatures(as_of=moment, **row) for row in rows.to_dict("records"))
            session.commit()


def reset_and_load(
    engine: Engine, scenario_set: str = "default", cfg: dict[str, Any] | None = None
) -> dict[str, int]:
    """Reset the database and the simulated clock, then load a scenario set.

    ``empty`` leaves the tables empty. ``default`` loads the generated v1 sellers, buyers, daily
    stats and trust features from ``data/synthetic/v1`` (run ``make data`` first). ``demo`` loads
    the same data; the demo scenarios are then set up by ``app.demo_scenarios`` through the API.
    """
    if scenario_set not in SCENARIO_SETS:
        raise ValueError(f"unknown scenario_set {scenario_set!r}")
    config = cfg or load_config()
    create_db(engine)
    reset_db(engine)
    if scenario_set == "empty":
        return {"sellers": 0, "buyers": 0}

    directory = REPO_ROOT / config["paths"]["synthetic_dir"] / "v1"
    needed = ("sellers.csv", "buyers.csv", "seller_daily_stats.csv")
    if not all((directory / name).exists() for name in needed):
        raise SyntheticDataMissing("generated data not found: run `make data` first")
    from app.trust.dataset import load_features

    sellers = pd.read_csv(directory / "sellers.csv")
    buyers = pd.read_csv(directory / "buyers.csv")
    stats = pd.read_csv(directory / "seller_daily_stats.csv")
    load_synthetic(
        engine, sellers, buyers, stats, load_features("v1"), config["generator"]["as_of"]
    )
    return {"sellers": len(sellers), "buyers": len(buyers)}
