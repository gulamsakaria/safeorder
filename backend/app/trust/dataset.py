"""Load a generated data version and its trust features (computed once, then cached)."""

from pathlib import Path

import pandas as pd

from app.config import load_config
from app.trust.features import FEATURE_COLUMNS, META_COLUMNS, compute_features

REPO_ROOT = Path(__file__).resolve().parents[3]
FEATURES_FILE = "seller_features.csv"


def version_dir(version: str) -> Path:
    return REPO_ROOT / load_config()["paths"]["synthetic_dir"] / version


def load_sellers(version: str) -> pd.DataFrame:
    return pd.read_csv(version_dir(version) / "sellers.csv").set_index("id", drop=False)


def load_features(version: str, refresh: bool = False) -> pd.DataFrame:
    """Features for every seller of a version, indexed by seller id (cached as a CSV)."""
    directory = version_dir(version)
    cache = directory / FEATURES_FILE
    if cache.exists() and not refresh:
        return pd.read_csv(cache, index_col="seller_id")[FEATURE_COLUMNS + META_COLUMNS]
    cfg = load_config()
    sellers = pd.read_csv(directory / "sellers.csv")
    orders = pd.read_csv(directory / "orders.csv", parse_dates=["placed_at"])
    stats = pd.read_csv(directory / "seller_daily_stats.csv")
    features = compute_features(
        sellers, orders, stats, cfg["generator"]["categories"], cfg["generator"]["as_of"], cfg
    )
    features.to_csv(cache, lineterminator="\n")
    return features
