"""Synthetic seller, buyer, order and daily-stats generator (BLUEPRINT.md Section 8.2).

Usage (from the repository root):
    PYTHONPATH=backend:. python -m scripts.generate_sellers --version both [--load-db]

All parameters come from config/config.yaml. The same seed always gives byte-identical files.
Everything is synthetic: names are "Synthetic Shop NNNN", wallet numbers start with SIM-W-.
"""

import argparse
import copy
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[1]
SECONDS_PER_DAY = 86_400
SECONDS_PER_HOUR = 3_600
UNIX_EPOCH_WEEKDAY = 3  # 1970-01-01 was a Thursday; Monday = 0
HIGH_RISK_ARCHETYPES = frozenset({"fake_burst", "slow_scammer", "collusive_ring"})
LATENCY_FLOOR_MIN = 1
RING_MIN_SIZE = 2
MAX_REPEAT_RATIO = 0.99


# ---- parameters ------------------------------------------------------------------------------


def _scaled(value: Any, factor: float) -> Any:
    if isinstance(value, list):
        return [_scaled(v, factor) for v in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return int(round(value * factor))
    return value * factor


def apply_scale(archetypes: dict[str, Any], scale: dict[str, float]) -> dict[str, Any]:
    """Return a copy of the archetype parameters with the dotted-path multipliers applied."""
    out = copy.deepcopy(archetypes)
    for path, factor in scale.items():
        archetype, key = path.split(".")
        out[archetype][key] = _scaled(out[archetype][key], factor)
    return out


def build_params(version: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    gen = (cfg or load_config())["generator"]
    if version not in gen["seeds"]:
        raise ValueError(f"unknown version {version!r}")
    params = {
        k: copy.deepcopy(v) for k, v in gen.items() if k not in ("v2", "archetypes", "shares")
    }
    params["version"] = version
    params["seed"] = gen["seeds"][version]
    if version == "v2":
        params["shares"] = copy.deepcopy(gen["v2"]["shares"])
        params["archetypes"] = apply_scale(gen["archetypes"], gen["v2"]["scale"])
    else:
        params["shares"] = copy.deepcopy(gen["shares"])
        params["archetypes"] = copy.deepcopy(gen["archetypes"])
    if abs(sum(params["shares"].values()) - 1.0) > 1e-9:
        raise ValueError("archetype shares must sum to 1")
    return params


def archetype_counts(shares: dict[str, float], n: int) -> dict[str, int]:
    """Largest-remainder rounding so the counts add up to n exactly."""
    raw = {a: s * n for a, s in shares.items()}
    counts = {a: math.floor(v) for a, v in raw.items()}
    leftover = n - sum(counts.values())
    for a in sorted(raw, key=lambda k: (-(raw[k] - counts[k]), k))[:leftover]:
        counts[a] += 1
    return counts


# ---- sampling helpers ------------------------------------------------------------------------


def _uniform(rng: np.random.Generator, bounds: list[float]) -> float:
    return float(rng.uniform(bounds[0], bounds[1]))


def _uniform_int(rng: np.random.Generator, bounds: list[int]) -> int:
    return int(rng.integers(bounds[0], bounds[1] + 1))


def _log_uniform(rng: np.random.Generator, bounds: list[float]) -> float:
    return float(math.exp(rng.uniform(math.log(bounds[0]), math.log(bounds[1]))))


def _prob(value: float) -> float:
    return min(1.0, max(0.0, value))


# ---- order building --------------------------------------------------------------------------


@dataclass
class Context:
    rng: np.random.Generator
    params: dict[str, Any]
    as_of_ts: int  # seconds since epoch of the scoring moment
    as_of_day: int  # days since epoch (the scoring moment is midnight starting this day)
    hour_p: np.ndarray
    festival_days: tuple[int, int]
    category_median: float
    buyer_pool: int


def _day_rates(ctx: Context, dates: np.ndarray, base: float | np.ndarray) -> np.ndarray:
    p = ctx.params
    weekday = (dates + UNIX_EPOCH_WEEKDAY) % 7
    factor = np.asarray(p["weekday_factors"])[weekday]
    start, end = ctx.festival_days
    festival = np.where((dates >= start) & (dates <= end), p["festival"]["multiplier"], 1.0)
    return base * factor * festival


def _timestamps(ctx: Context, dates: np.ndarray, counts: np.ndarray) -> np.ndarray:
    n = int(counts.sum())
    days = np.repeat(dates, counts)
    hours = ctx.rng.choice(24, size=n, p=ctx.hour_p)
    seconds = ctx.rng.integers(0, SECONDS_PER_HOUR, n)
    return days * SECONDS_PER_DAY + hours * SECONDS_PER_HOUR + seconds


def _draw_buyers(
    ctx: Context,
    n: int,
    repeat_ratio: float,
    ring_pool: np.ndarray | None = None,
    ring_share: float = 0.0,
) -> np.ndarray:
    """Pick a buyer per order so the share of buyers with 2+ orders is about ``repeat_ratio``.

    Returning buyers average ``loyal_orders_per_buyer`` orders each, so for n orders and ratio r
    there are L = n / (k + (1 - r) / r) returning buyers and the rest are one-off buyers.
    A collusive ring instead sends ``ring_share`` of its orders to a small shared buyer pool.
    """
    rng = ctx.rng
    fresh = rng.integers(0, ctx.buyer_pool, n)
    if n == 0:
        return fresh
    if ring_pool is not None:
        loyal_pool, share = ring_pool, ring_share
    else:
        ratio = min(max(repeat_ratio, 0.0), MAX_REPEAT_RATIO)
        if ratio <= 0.0:
            return fresh
        k = ctx.params["loyal_orders_per_buyer"]
        loyal_n = n / (k + (1.0 - ratio) / ratio)
        share = min(1.0, loyal_n * k / n)
        loyal_pool = rng.integers(0, ctx.buyer_pool, max(1, round(loyal_n)))
    loyal = loyal_pool[rng.integers(0, len(loyal_pool), n)]
    return np.where(rng.random(n) < share, loyal, fresh)


def _finalize(
    ctx: Context,
    ts: np.ndarray,
    buyers: np.ndarray,
    ticket: np.ndarray,
    refund_p: np.ndarray,
    dispute_p: np.ndarray,
    cashout_median: np.ndarray,
    cashout_sigma: float,
) -> dict[str, np.ndarray]:
    rng, p = ctx.rng, ctx.params
    n = len(ts)
    noise = np.exp(rng.normal(0.0, p["ticket_sigma"], n))
    amount = ctx.category_median * ticket * noise
    step = p["amount_round_to"]
    amount = np.maximum(p["min_amount_bdt"], np.round(amount / step) * step).astype(np.int64)
    latency = np.exp(np.log(cashout_median) + rng.normal(0.0, cashout_sigma, n))
    latency = np.clip(latency, LATENCY_FLOOR_MIN, p["max_cashout_latency_min"]).astype(np.int64)
    return {
        "ts": ts,
        "buyer": buyers,
        "amount_bdt": amount,
        "refunded": (rng.random(n) < refund_p).astype(np.int64),
        "disputed": (rng.random(n) < dispute_p).astype(np.int64),
        "cashout_latency_min": latency,
    }


def _from_daily(
    ctx: Context,
    window: int,
    rates: np.ndarray,
    dates: np.ndarray,
    repeat_ratio: float,
    ticket: np.ndarray,
    refund_p: np.ndarray,
    dispute_p: np.ndarray,
    cashout_median: np.ndarray,
    sigma: float,
    ring_pool: np.ndarray | None = None,
    ring_share: float = 0.0,
) -> dict[str, np.ndarray]:
    counts = ctx.rng.poisson(rates)
    ts = _timestamps(ctx, dates, counts)
    buyers = _draw_buyers(ctx, len(ts), repeat_ratio, ring_pool, ring_share)
    rep = lambda arr: np.repeat(arr, counts)  # noqa: E731
    return _finalize(
        ctx, ts, buyers, rep(ticket), rep(refund_p), rep(dispute_p), rep(cashout_median), sigma
    )


def _flat(window: int, value: float) -> np.ndarray:
    return np.full(window, value, dtype=float)


def _window_dates(ctx: Context, age: int) -> tuple[int, np.ndarray]:
    window = min(age, _uniform_int(ctx.rng, ctx.params["stats_window_days"]))
    return window, ctx.as_of_day - window + np.arange(window)


def _steady(
    ctx: Context, spec: dict[str, Any], ring_pool: np.ndarray | None = None
) -> tuple[int, int, dict]:
    """Shared builder for honest_established, honest_new, chronic_poor_service, collusive_ring."""
    rng = ctx.rng
    age = _uniform_int(rng, spec["age_days"])
    window, dates = _window_dates(ctx, age)
    rates = _day_rates(ctx, dates, _log_uniform(rng, spec["orders_per_day"]))
    median = _log_uniform(rng, spec["cashout_median_min"])
    if "fast_cashout_prob" in spec and rng.random() < _prob(spec["fast_cashout_prob"]):
        median = _log_uniform(rng, spec["fast_cashout_median_min"])
    ring_share = _uniform(rng, spec["ring_share"]) if ring_pool is not None else 0.0
    repeat = _uniform(rng, spec["repeat_buyer_ratio"]) if "repeat_buyer_ratio" in spec else 0.0
    orders = _from_daily(
        ctx, window, rates, dates, repeat,
        _flat(window, _uniform(rng, spec["ticket_ratio"])),
        _flat(window, _uniform(rng, spec["refund_rate"])),
        _flat(window, _uniform(rng, spec["dispute_rate"])),
        _flat(window, median), spec["cashout_sigma"], ring_pool, ring_share,
    )  # fmt: skip
    return age, window, orders


def _fake_burst(ctx: Context, spec: dict[str, Any]) -> tuple[int, int, dict]:
    rng = ctx.rng
    age = _uniform_int(rng, spec["age_days"])
    mild = rng.random() < _prob(spec["mild_prob"])
    burst_hours = min(_uniform_int(rng, spec["burst_hours"]), age * 24)
    n_buyers = _uniform_int(rng, spec["mild_burst_buyers"] if mild else spec["burst_buyers"])
    n_orders = n_buyers + int(rng.integers(0, n_buyers // 10 + 1))
    burst_start = ctx.as_of_ts - burst_hours * SECONDS_PER_HOUR
    burst_ts = rng.integers(burst_start, ctx.as_of_ts, n_orders)
    buyers = rng.choice(ctx.buyer_pool, size=n_buyers, replace=False)
    burst_buyers = np.concatenate([buyers, rng.choice(buyers, size=n_orders - n_buyers)])

    history_start = ctx.as_of_ts - age * SECONDS_PER_DAY
    k = _uniform_int(rng, spec["pre_burst_orders"]) if history_start < burst_start else 0
    pre_ts = rng.integers(history_start, burst_start, k) if k else np.empty(0, dtype=np.int64)
    pre_buyers = rng.integers(0, ctx.buyer_pool, k)

    ts = np.concatenate([pre_ts, burst_ts]).astype(np.int64)
    all_buyers = np.concatenate([pre_buyers, burst_buyers])
    n = len(ts)
    ticket = _uniform(rng, spec["mild_ticket_ratio"] if mild else spec["ticket_ratio"])
    median = _log_uniform(
        rng, spec["mild_cashout_median_min"] if mild else spec["cashout_median_min"]
    )
    orders = _finalize(
        ctx, ts, all_buyers, _flat(n, ticket),
        _flat(n, _uniform(rng, spec["refund_rate"])),
        _flat(n, _uniform(rng, spec["dispute_rate"])),
        _flat(n, median), spec["cashout_sigma"],
    )  # fmt: skip
    return age, age, orders


def _slow_scammer(ctx: Context, spec: dict[str, Any]) -> tuple[int, int, dict]:
    rng = ctx.rng
    honest = _uniform_int(rng, spec["honest_days"])
    spike = _uniform_int(rng, spec["spike_days"])
    silence = _uniform_int(rng, spec["silence_days"])
    age = honest + spike + silence
    window, dates = _window_dates(ctx, age)
    since_creation = age - window + np.arange(window)
    in_spike = (since_creation >= honest) & (since_creation < honest + spike)
    in_silence = since_creation >= honest + spike

    mild = rng.random() < _prob(spec["mild_prob"])
    multiplier = _uniform(
        rng, spec["mild_spike_order_multiplier" if mild else "spike_order_multiplier"]
    )
    base = _log_uniform(rng, spec["honest_orders_per_day"])
    rates = _day_rates(ctx, dates, np.where(in_spike, base * multiplier, base))
    rates = np.where(in_silence, 0.0, rates)

    def pick(honest_key: str, spike_key: str, log: bool = False) -> np.ndarray:
        draw = _log_uniform if log else _uniform
        return np.where(in_spike, draw(rng, spec[spike_key]), draw(rng, spec[honest_key]))

    orders = _from_daily(
        ctx, window, rates, dates, _uniform(rng, spec["repeat_buyer_ratio"]),
        pick("honest_ticket_ratio", "spike_ticket_ratio"),
        pick("honest_refund_rate", "spike_refund_rate"),
        pick("honest_dispute_rate", "spike_dispute_rate"),
        pick("honest_cashout_median_min", "spike_cashout_median_min", log=True),
        spec["cashout_sigma"],
    )  # fmt: skip
    return age, window, orders


# ---- generation ------------------------------------------------------------------------------


@dataclass
class GeneratedData:
    version: str
    params: dict[str, Any]
    sellers: pd.DataFrame
    buyers: pd.DataFrame
    orders: pd.DataFrame
    daily_stats: pd.DataFrame


def _ring_groups(
    rng: np.random.Generator, members: list[int], size_range: list[int]
) -> list[list[int]]:
    groups: list[list[int]] = []
    i = 0
    while i < len(members):
        size = _uniform_int(rng, size_range)
        groups.append(members[i : i + size])
        i += size
    if len(groups) > 1 and len(groups[-1]) < RING_MIN_SIZE:
        groups[-2].extend(groups.pop())
    return groups


def _buyer_id(index: np.ndarray | int) -> Any:
    digits = (np.asarray(index) + 1).astype(str)
    return np.char.add("B-", np.char.zfill(digits, 6))


def generate(
    version: str, cfg: dict[str, Any] | None = None, n_sellers: int | None = None
) -> GeneratedData:
    params = build_params(version, cfg)
    rng = np.random.default_rng(params["seed"])
    n = n_sellers if n_sellers is not None else params["n_sellers"]
    as_of = datetime.fromisoformat(params["as_of"])
    as_of_ts = int(as_of.replace(tzinfo=UTC).timestamp())
    festival = (
        date.fromisoformat(params["festival"]["start"]).toordinal() - date(1970, 1, 1).toordinal(),
        date.fromisoformat(params["festival"]["end"]).toordinal() - date(1970, 1, 1).toordinal(),
    )
    hour_p = np.asarray(params["hour_weights"], dtype=float)
    hour_p = hour_p / hour_p.sum()
    categories = list(params["categories"])

    counts = archetype_counts(params["shares"], n)
    archetypes = np.array([a for a, c in counts.items() for _ in range(c)])
    rng.shuffle(archetypes)

    ring_of: dict[int, int] = {}
    ring_pools: dict[int, np.ndarray] = {}
    spec_ring = params["archetypes"]["collusive_ring"]
    members = [i for i, a in enumerate(archetypes) if a == "collusive_ring"]
    for ring_id, group in enumerate(_ring_groups(rng, members, spec_ring["ring_size"]), start=1):
        size = _uniform_int(rng, spec_ring["ring_pool_buyers"])
        ring_pools[ring_id] = rng.integers(0, params["buyer_pool_size"], size)
        for idx in group:
            ring_of[idx] = ring_id

    seller_rows: list[dict[str, Any]] = []
    order_frames: list[pd.DataFrame] = []
    window_days: list[int] = []
    for idx, archetype in enumerate(archetypes):
        sid = f"S-{idx + 1:04d}"
        category = categories[int(rng.integers(0, len(categories)))]
        ctx = Context(
            rng=rng, params=params, as_of_ts=as_of_ts, as_of_day=as_of_ts // SECONDS_PER_DAY,
            hour_p=hour_p, festival_days=festival,
            category_median=float(params["categories"][category]),
            buyer_pool=params["buyer_pool_size"],
        )  # fmt: skip
        spec = params["archetypes"][archetype]
        if archetype == "fake_burst":
            age, window, orders = _fake_burst(ctx, spec)
        elif archetype == "slow_scammer":
            age, window, orders = _slow_scammer(ctx, spec)
        elif archetype == "collusive_ring":
            age, window, orders = _steady(ctx, spec, ring_pools[ring_of[idx]])
        else:
            age, window, orders = _steady(ctx, spec)
        clean_label = archetype in HIGH_RISK_ARCHETYPES
        flipped = bool(rng.random() < params["label_noise"])
        seller_rows.append(
            {
                "id": sid,
                "display_name": f"Synthetic Shop {idx + 1:04d}",
                "wallet_no": f"SIM-W-S{idx + 1:04d}",
                "created_at": (as_of - timedelta(days=age)).isoformat(timespec="seconds"),
                "category": category,
                "archetype": archetype,
                "is_high_risk": int(clean_label != flipped),
                "label_noised": int(flipped),
                "ring_id": ring_of.get(idx, 0),
                "account_age_days": age,
                "stats_days": window,
            }
        )
        window_days.append(window)
        frame = pd.DataFrame(orders)
        frame.insert(0, "seller_id", sid)
        order_frames.append(frame)

    sellers = pd.DataFrame(seller_rows)
    raw = pd.concat(order_frames, ignore_index=True)
    raw["buyer_id"] = _buyer_id(raw["buyer"].to_numpy())
    raw["placed_at"] = pd.to_datetime(raw["ts"], unit="s")
    orders = raw[
        ["seller_id", "buyer_id", "placed_at", "amount_bdt", "refunded", "disputed",
         "cashout_latency_min"]
    ].sort_values(["seller_id", "placed_at", "buyer_id", "amount_bdt"], kind="stable")  # fmt: skip
    orders = orders.reset_index(drop=True)

    buyer_ids = np.sort(orders["buyer_id"].unique())
    buyer_age = rng.integers(
        params["buyer_age_days"][0], params["buyer_age_days"][1] + 1, len(buyer_ids)
    )
    buyers = pd.DataFrame(
        {
            "id": buyer_ids,
            "display_name": [f"Synthetic Buyer {b[2:]}" for b in buyer_ids],
            "wallet_no": [f"SIM-W-{b.replace('-', '')}" for b in buyer_ids],
            "created_at": [
                (as_of - timedelta(days=int(a))).isoformat(timespec="seconds") for a in buyer_age
            ],
        }
    )
    daily = _daily_stats(sellers, orders, as_of)
    return GeneratedData(version, params, sellers, buyers, orders, daily)


def _daily_stats(sellers: pd.DataFrame, orders: pd.DataFrame, as_of: datetime) -> pd.DataFrame:
    as_of_day = pd.Timestamp(as_of).normalize()
    orders = orders.assign(
        day=orders["placed_at"].dt.normalize(),
        cashout_day=(
            orders["placed_at"] + pd.to_timedelta(orders["cashout_latency_min"], unit="m")
        ).dt.normalize(),
    )
    by_day = orders.groupby(["seller_id", "day"]).agg(
        orders=("buyer_id", "size"),
        unique_buyers=("buyer_id", "nunique"),
        inflow_bdt=("amount_bdt", "sum"),
        refunds=("refunded", "sum"),
        disputes=("disputed", "sum"),
    )
    cashed = orders[orders["cashout_day"] < as_of_day]
    cash = cashed.groupby(["seller_id", "cashout_day"])["amount_bdt"].sum().rename("cashout_bdt")
    cash.index = cash.index.set_names(["seller_id", "day"])

    days = sellers["stats_days"].to_numpy()
    grid = pd.DataFrame(
        {
            "seller_id": np.repeat(sellers["id"].to_numpy(), days),
            "day": np.concatenate(
                [as_of_day - pd.to_timedelta(np.arange(d, 0, -1), unit="D") for d in days]
            ),
        }
    )
    stats = grid.merge(by_day.reset_index(), how="left", on=["seller_id", "day"])
    stats = stats.merge(cash.reset_index(), how="left", on=["seller_id", "day"])
    columns = ["orders", "unique_buyers", "inflow_bdt", "cashout_bdt", "refunds", "disputes"]
    stats[columns] = stats[columns].fillna(0).astype(np.int64)
    stats = stats.rename(columns={"day": "date"})
    stats["date"] = stats["date"].dt.strftime("%Y-%m-%d")
    return stats[["seller_id", "date", *columns]]


# ---- output, summary and database loading -----------------------------------------------------


def _csv_ready(data: GeneratedData) -> dict[str, pd.DataFrame]:
    orders = data.orders.assign(placed_at=data.orders["placed_at"].dt.strftime("%Y-%m-%dT%H:%M:%S"))
    return {
        "sellers.csv": data.sellers,
        "buyers.csv": data.buyers,
        "orders.csv": orders,
        "seller_daily_stats.csv": data.daily_stats,
    }


def write_outputs(data: GeneratedData, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, Any] = {}
    for name, frame in _csv_ready(data).items():
        path = out_dir / name
        frame.to_csv(path, index=False, lineterminator="\n")
        files[name] = {"rows": len(frame), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = {"version": data.version, "seed": data.params["seed"], "files": files}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def summarize(data: GeneratedData) -> dict[str, Any]:
    """Realised statistics per archetype, measured on the generated data (not the inputs)."""
    p = data.params
    orders = data.orders.merge(
        data.sellers[["id", "archetype", "category"]], left_on="seller_id", right_on="id"
    )
    median = orders["category"].map(p["categories"]).astype(float)
    orders["ticket_ratio"] = orders["amount_bdt"] / median
    as_of = pd.Timestamp(p["as_of"])
    last_24h = orders[orders["placed_at"] >= as_of - pd.Timedelta(hours=24)]
    per_seller = orders.groupby("seller_id")
    buyers_per_seller = per_seller["buyer_id"].nunique()
    repeat = orders.groupby(["seller_id", "buyer_id"]).size().ge(2).groupby("seller_id").mean()
    seller_stats = (
        pd.DataFrame(
            {
                "orders": per_seller.size(),
                "unique_buyers": buyers_per_seller,
                "repeat_buyer_ratio": repeat,
                "refund_rate": per_seller["refunded"].mean(),
                "dispute_rate": per_seller["disputed"].mean(),
                "median_cashout_min": per_seller["cashout_latency_min"].median(),
                "mean_ticket_ratio": per_seller["ticket_ratio"].mean(),
                "unique_buyers_24h": last_24h.groupby("seller_id")["buyer_id"].nunique(),
            }
        )
        .reindex(data.sellers["id"])
        .fillna(0.0)
    )
    seller_stats["archetype"] = data.sellers["archetype"].to_numpy()
    seller_stats["age"] = data.sellers["account_age_days"].to_numpy()
    grouped = seller_stats.groupby("archetype")
    table = grouped.mean(numeric_only=True).round(3)
    table.insert(0, "sellers", grouped.size())
    table.insert(1, "share", (grouped.size() / len(data.sellers)).round(4))
    return {
        "version": data.version,
        "n_sellers": len(data.sellers),
        "n_orders": len(data.orders),
        "label_noise_realised": round(float(data.sellers["label_noised"].mean()), 4),
        "high_risk_share": round(float(data.sellers["is_high_risk"].mean()), 4),
        "per_archetype": json.loads(table.to_json(orient="index")),
    }


def load_into_db(data: GeneratedData, engine: Any) -> None:
    """Load sellers, buyers and daily stats for the demo. Orders and ledger stay in CSV files."""
    from sqlalchemy import insert
    from sqlmodel import Session

    from app.models import Buyer, Seller, SellerDailyStats

    def aware(text: str) -> datetime:
        return datetime.fromisoformat(text).replace(tzinfo=UTC)

    with Session(engine) as session:
        session.add_all(
            Seller(
                id=r.id, display_name=r.display_name, wallet_no=r.wallet_no,
                created_at=aware(r.created_at), category=r.category, archetype=r.archetype,
                is_high_risk=bool(r.is_high_risk),
            )
            for r in data.sellers.itertuples()
        )  # fmt: skip
        session.add_all(
            Buyer(id=r.id, display_name=r.display_name, wallet_no=r.wallet_no,
                  created_at=aware(r.created_at))
            for r in data.buyers.itertuples()
        )  # fmt: skip
        session.commit()
        rows = data.daily_stats.assign(date=lambda f: pd.to_datetime(f["date"]).dt.date).rename(
            columns={"seller_id": "seller_id"}
        )
        records = rows.to_dict(orient="records")
        chunk = 20_000
        for start in range(0, len(records), chunk):
            session.execute(insert(SellerDailyStats), records[start : start + chunk])
        session.commit()


def write_assumptions_doc(path: Path, reports_dir: Path) -> None:
    gen = load_config()["generator"]
    lines = [
        "# Synthetic data assumptions (seller behaviour generator)",
        "",
        "Generated by `scripts/generate_sellers.py` from `config/config.yaml`.",
        "Do not edit by hand.",
        "",
        "**All data here is synthetic. It is not validated on real data and makes no claim about",
        "how real Facebook-commerce sellers behave.** Every parameter below is an assumption.",
        "",
        "## Global parameters",
        "",
        "```yaml",
        *_yaml_lines({k: v for k, v in gen.items() if k not in ("archetypes", "v2", "shares")}),
        "```",
        "",
        "## Archetype mix and behaviour (generator v1, used for training)",
        "",
        "```yaml",
        *_yaml_lines({"shares": gen["shares"], "archetypes": gen["archetypes"]}),
        "```",
        "",
        "## Generator v2 (shifted parameters, used for testing)",
        "",
        "```yaml",
        *_yaml_lines(gen["v2"]),
        "```",
        "",
        "## Known simplifications",
        "",
        "- Weekday factors, the festival spike and the hourly profile are made up.",
        "- Label noise flips `is_high_risk` for a fixed share of sellers at random.",
        "- Overlaps (mild bursts, fast honest cash-out, mild slow-scammer spikes) keep the task",
        "  from being trivially separable, but the real overlap is unknown.",
        "- Money, accounts, names and wallet numbers are fictional (`SIM-W-` prefix).",
        "- Orders are kept in CSV files; only sellers, buyers and daily stats go into the demo",
        "  database.",
        "",
    ]
    for version in ("v1", "v2"):
        report = reports_dir / f"synthetic_summary_{version}.json"
        if not report.exists():
            continue
        summary = json.loads(report.read_text())
        lines += [
            f"## Realised statistics, {version}",
            "",
            f"Sellers: {summary['n_sellers']}, orders: {summary['n_orders']}, "
            f"high-risk share (after label noise): {summary['high_risk_share']}, "
            f"realised label noise: {summary['label_noise_realised']}.",
            "",
        ]
        table = pd.DataFrame(summary["per_archetype"]).T
        columns = list(table.columns)
        lines.append("| archetype | " + " | ".join(columns) + " |")
        lines.append("|---|" + "---|" * len(columns))
        for name, row in table.iterrows():
            lines.append(f"| {name} | " + " | ".join(str(row[c]) for c in columns) + " |")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def _yaml_lines(obj: dict[str, Any]) -> list[str]:
    import yaml

    return yaml.safe_dump(obj, sort_keys=False, default_flow_style=None, width=100).splitlines()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=["v1", "v2", "both"], default="both")
    parser.add_argument("--n-sellers", type=int, default=None)
    parser.add_argument("--load-db", action="store_true", help="load v1 sellers into the demo DB")
    args = parser.parse_args()

    cfg = load_config()
    out_root = REPO_ROOT / cfg["paths"]["synthetic_dir"]
    reports = REPO_ROOT / cfg["paths"]["reports_dir"]
    reports.mkdir(parents=True, exist_ok=True)
    versions = ["v1", "v2"] if args.version == "both" else [args.version]
    for version in versions:
        data = generate(version, cfg, args.n_sellers)
        manifest = write_outputs(data, out_root / version)
        summary = summarize(data)
        (reports / f"synthetic_summary_{version}.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n"
        )
        print(f"\n== {version}: {summary['n_sellers']} sellers, {summary['n_orders']} orders ==")
        print(pd.DataFrame(summary["per_archetype"]).T.to_string())
        print({name: info["sha256"][:12] for name, info in manifest["files"].items()})
        if args.load_db and version == "v1":
            from app.db import create_db, make_engine, reset_db

            engine = make_engine()
            create_db(engine)
            reset_db(engine)
            load_into_db(data, engine)
            print("loaded v1 sellers, buyers and daily stats into the demo database")
    write_assumptions_doc(
        REPO_ROOT / cfg["paths"]["docs_dir"] / "synthetic_assumptions.md", reports
    )


if __name__ == "__main__":
    main()
