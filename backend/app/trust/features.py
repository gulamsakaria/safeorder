"""Trust features per seller (BLUEPRINT.md Section 8.2), computed with pandas.

Inputs are plain DataFrames so the same code serves the generator output (CSV files) and tests.
All windows end at ``as_of``. Sellers without orders get zeros, except the two features that
need at least one order (cash-out latency and ticket ratio), which stay missing (NaN).
"""

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse

from app.config import load_config

FEATURE_COLUMNS: list[str] = [
    "account_age_days",
    "orders_7d",
    "orders_30d",
    "unique_buyers_24h",
    "unique_buyers_30d",
    "buyer_burst_ratio",
    "repeat_buyer_ratio",
    "buyer_concentration",
    "refund_rate",
    "dispute_rate",
    "median_cashout_latency_min",
    "ticket_vs_category_ratio",
    "shared_buyer_overlap",
]
META_COLUMNS: list[str] = ["orders_total", "refund_count", "dispute_count"]

HOURS_24 = pd.Timedelta(hours=24)
DAYS_7 = pd.Timedelta(days=7)
DAYS_30 = pd.Timedelta(days=30)
REPEAT_MIN_ORDERS = 2


def _windowed(orders: pd.DataFrame, as_of: pd.Timestamp, span: pd.Timedelta) -> pd.DataFrame:
    return orders[orders["placed_at"] >= as_of - span]


def shared_buyer_overlap(orders: pd.DataFrame, seller_ids: pd.Index, min_buyers: int) -> pd.Series:
    """Largest share of a seller's buyers who also paid one single other seller.

    A simple pandas/scipy version of cluster detection (graph methods are P2). Sellers with
    fewer than ``min_buyers`` distinct buyers get 0, because a share over one or two buyers is
    noise (a single buyer shared with anyone would give 100%).
    """
    pairs = orders[["seller_id", "buyer_id"]].drop_duplicates()
    rows = seller_ids.get_indexer(pairs["seller_id"])
    buyer_codes, _ = pd.factorize(pairs["buyer_id"])
    n_sellers, n_buyers = len(seller_ids), int(buyer_codes.max(initial=-1)) + 1
    incidence = sparse.csr_matrix(
        (np.ones(len(pairs), dtype=np.int32), (rows, buyer_codes)), shape=(n_sellers, n_buyers)
    )
    shared = (incidence @ incidence.T).tolil()
    shared.setdiag(0)
    shared = shared.tocsr()
    shared.eliminate_zeros()
    buyers_per_seller = np.asarray(incidence.sum(axis=1)).ravel()
    best = shared.max(axis=1).toarray().ravel()
    with np.errstate(divide="ignore", invalid="ignore"):
        overlap = np.where(buyers_per_seller >= min_buyers, best / buyers_per_seller, 0.0)
    return pd.Series(overlap, index=seller_ids)


def compute_features(
    sellers: pd.DataFrame,
    orders: pd.DataFrame,
    daily_stats: pd.DataFrame,
    categories: dict[str, float],
    as_of: datetime | pd.Timestamp,
    cfg: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Return one row per seller: FEATURE_COLUMNS followed by META_COLUMNS."""
    model_cfg = (cfg or load_config())["trust_model"]
    as_of = pd.Timestamp(as_of)
    ids = pd.Index(sellers["id"], name="seller_id")
    orders = orders[orders["placed_at"] < as_of]
    by_seller = orders.groupby("seller_id")

    def count(frame: pd.DataFrame) -> pd.Series:
        return frame.groupby("seller_id").size().reindex(ids, fill_value=0)

    def unique(frame: pd.DataFrame) -> pd.Series:
        return frame.groupby("seller_id")["buyer_id"].nunique().reindex(ids, fill_value=0)

    out = pd.DataFrame(index=ids)
    created = pd.to_datetime(sellers.set_index("id")["created_at"]).reindex(ids)
    out["account_age_days"] = (as_of - created).dt.total_seconds() / 86_400
    out["orders_7d"] = count(_windowed(orders, as_of, DAYS_7))
    out["orders_30d"] = count(_windowed(orders, as_of, DAYS_30))
    out["unique_buyers_24h"] = unique(_windowed(orders, as_of, HOURS_24))
    out["unique_buyers_30d"] = unique(_windowed(orders, as_of, DAYS_30))

    stats = daily_stats.assign(date=pd.to_datetime(daily_stats["date"]))
    recent = stats[stats["date"] >= as_of.normalize() - DAYS_30]
    daily_average = recent.groupby("seller_id")["unique_buyers"].mean().reindex(ids, fill_value=0.0)
    out["buyer_burst_ratio"] = out["unique_buyers_24h"] / daily_average.clip(
        lower=model_cfg["burst_ratio_floor"]
    )

    per_buyer = orders.groupby(["seller_id", "buyer_id"]).size().rename("n").reset_index()
    per_buyer["share"] = per_buyer["n"] / per_buyer.groupby("seller_id")["n"].transform("sum")
    repeat = (per_buyer["n"] >= REPEAT_MIN_ORDERS).groupby(per_buyer["seller_id"]).mean()
    herfindahl = (per_buyer["share"] ** 2).groupby(per_buyer["seller_id"]).sum()
    out["repeat_buyer_ratio"] = repeat.reindex(ids, fill_value=0.0)
    out["buyer_concentration"] = herfindahl.reindex(ids, fill_value=0.0)

    out["refund_rate"] = by_seller["refunded"].mean().reindex(ids, fill_value=0.0)
    out["dispute_rate"] = by_seller["disputed"].mean().reindex(ids, fill_value=0.0)
    out["median_cashout_latency_min"] = by_seller["cashout_latency_min"].median().reindex(ids)

    category_median = sellers.set_index("id")["category"].map(categories).astype(float).reindex(ids)
    out["ticket_vs_category_ratio"] = by_seller["amount_bdt"].mean().reindex(ids) / category_median
    out["shared_buyer_overlap"] = shared_buyer_overlap(orders, ids, model_cfg["overlap_min_buyers"])

    out["orders_total"] = count(orders)
    out["refund_count"] = by_seller["refunded"].sum().reindex(ids, fill_value=0).astype(int)
    out["dispute_count"] = by_seller["disputed"].sum().reindex(ids, fill_value=0).astype(int)
    return out[FEATURE_COLUMNS + META_COLUMNS]
