import json
import re
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
from sqlmodel import Session, func, select

from app.clock import SimClock
from app.config import load_config
from app.db import create_db, make_engine
from app.enums import TrustBand
from app.models import SellerFeatures
from app.trust import reasons as rs
from app.trust.features import (
    FEATURE_COLUMNS,
    META_COLUMNS,
    compute_features,
    shared_buyer_overlap,
)
from app.trust.model import TrustModel, split_indices, train_model
from scripts import generate_sellers as gs

AS_OF = pd.Timestamp("2026-10-01")
CATEGORIES = {"shoes": 1000.0}


def _ts(text: str) -> pd.Timestamp:
    return pd.Timestamp(text)


# ---- features on a hand-made example ---------------------------------------------------------


@pytest.fixture()
def hand_made() -> pd.DataFrame:
    sellers = pd.DataFrame(
        {"id": ["S-1", "S-2"], "created_at": ["2026-09-21T00:00:00", "2026-01-01T00:00:00"],
         "category": ["shoes", "shoes"]}
    )  # fmt: skip
    rows = [
        ("S-1", "A", "2026-09-30 20:00", 1000, 0, 0, 30),
        ("S-1", "A", "2026-09-30 10:00", 1000, 1, 0, 90),
        ("S-1", "B", "2026-09-28 12:00", 2000, 0, 1, 600),
        ("S-1", "C", "2026-09-10 12:00", 1000, 0, 0, 60),
        ("S-1", "D", "2026-08-20 12:00", 1000, 0, 0, 60),
    ]
    orders = pd.DataFrame(
        rows,
        columns=["seller_id", "buyer_id", "placed_at", "amount_bdt", "refunded", "disputed",
                 "cashout_latency_min"],
    )  # fmt: skip
    orders["placed_at"] = pd.to_datetime(orders["placed_at"])
    days = pd.date_range("2026-09-21", "2026-09-30")
    stats = pd.DataFrame(
        {"seller_id": "S-1", "date": days.strftime("%Y-%m-%d"),
         "unique_buyers": [0] * 9 + [1]}
    )  # fmt: skip
    return sellers, orders, stats


def test_features_match_hand_computation(hand_made) -> None:
    sellers, orders, stats = hand_made
    f = compute_features(sellers, orders, stats, CATEGORIES, AS_OF)
    row = f.loc["S-1"]
    assert list(f.columns) == FEATURE_COLUMNS + META_COLUMNS
    assert row["account_age_days"] == 10
    assert (row["orders_7d"], row["orders_30d"]) == (3, 4)
    assert (row["unique_buyers_24h"], row["unique_buyers_30d"]) == (1, 3)
    assert row["buyer_burst_ratio"] == pytest.approx(1.0)  # 1 buyer / max(0.1 daily avg, floor 1)
    assert row["repeat_buyer_ratio"] == pytest.approx(0.25)  # only buyer A ordered twice of 4
    assert row["buyer_concentration"] == pytest.approx(0.28)  # 0.4^2 + 3 * 0.2^2
    assert row["refund_rate"] == pytest.approx(0.2)
    assert row["dispute_rate"] == pytest.approx(0.2)
    assert row["median_cashout_latency_min"] == 60
    assert row["ticket_vs_category_ratio"] == pytest.approx(1.2)
    assert (row["orders_total"], row["refund_count"], row["dispute_count"]) == (5, 1, 1)


def test_seller_without_orders_gets_zeros_and_missing_values(hand_made) -> None:
    sellers, orders, stats = hand_made
    row = compute_features(sellers, orders, stats, CATEGORIES, AS_OF).loc["S-2"]
    assert row["orders_total"] == 0 and row["repeat_buyer_ratio"] == 0
    assert np.isnan(row["median_cashout_latency_min"])
    assert np.isnan(row["ticket_vs_category_ratio"])


def test_orders_after_the_scoring_moment_are_ignored(hand_made) -> None:
    sellers, orders, stats = hand_made
    late = orders.iloc[[0]].assign(placed_at=_ts("2026-10-02 00:00"))
    f = compute_features(sellers, pd.concat([orders, late]), stats, CATEGORIES, AS_OF)
    assert f.loc["S-1", "orders_total"] == 5


def test_shared_buyer_overlap_and_minimum_buyers() -> None:
    def rows(seller: str, buyers: list[int]) -> list[tuple[str, str]]:
        return [(seller, f"B-{b}") for b in buyers]

    pairs = rows("X", [1, 2, 3, 4, 5, 6]) + rows("Y", [1, 2, 3, 4, 5, 6])
    pairs += rows("Z", [7, 8, 9, 10, 11, 12]) + rows("W", [1])
    orders = pd.DataFrame(pairs, columns=["seller_id", "buyer_id"])
    out = shared_buyer_overlap(orders, pd.Index(["X", "Y", "Z", "W"]), min_buyers=5)
    assert out.to_dict() == {"X": 1.0, "Y": 1.0, "Z": 0.0, "W": 0.0}  # W: too few buyers


# ---- reasons and translations ----------------------------------------------------------------


def test_catalogs_are_complete_and_consistent() -> None:
    en, bn = rs.catalog("en"), rs.catalog("bn")
    needed = set(rs.REASON_KEYS.values()) | {
        "GENERIC_RISK",
        "GENERIC_PROTECTIVE",
        "LIMITED_HISTORY",
    }
    assert needed <= set(en["reasons"]) and set(en["reasons"]) == set(bn["reasons"])
    assert set(FEATURE_COLUMNS) <= set(en["labels"]) and set(en["labels"]) == set(bn["labels"])
    for key, text in en["reasons"].items():
        assert set(re.findall(r"{(\w+)}", text)) == set(re.findall(r"{(\w+)}", bn["reasons"][key]))
    assert all(re.search(r"[ঀ-৿]", t) for t in bn["reasons"].values())


def test_value_formatting_in_both_languages() -> None:
    assert rs.render("FAST_CASHOUT", "median_cashout_latency_min", 13, "en").endswith(
        "13 minutes of arriving"
    )
    assert "১৩ মিনিট" in rs.render("FAST_CASHOUT", "median_cashout_latency_min", 13, "bn")
    assert "3 days" in rs.render("NORMAL_CASHOUT_RHYTHM", "median_cashout_latency_min", 4400, "en")
    assert "62" not in rs.render("BUYER_BURST", "unique_buyers_24h", 62, "bn")  # Bengali digits
    assert "৬২" in rs.render("BUYER_BURST", "unique_buyers_24h", 62, "bn")


def _values_and_contrib() -> tuple[dict, dict, dict]:
    values = {c: 1.0 for c in FEATURE_COLUMNS}
    values["median_cashout_latency_min"] = 13.0
    contrib = {c: 0.0 for c in FEATURE_COLUMNS}
    contrib.update(
        median_cashout_latency_min=1.4, unique_buyers_24h=1.1, account_age_days=0.9,
        repeat_buyer_ratio=0.5, refund_rate=-0.4, dispute_rate=0.02,
    )  # fmt: skip
    medians = {c: 5.0 for c in FEATURE_COLUMNS}
    medians["median_cashout_latency_min"] = 3000.0  # 13 minutes is far below the typical value
    return values, contrib, medians


def test_build_reasons_picks_two_to_four_strongest_in_the_verdict_direction() -> None:
    values, contrib, medians = _values_and_contrib()
    out = rs.build_reasons(values, contrib, medians, score=15)
    assert 2 <= len(out) <= 4
    assert [r.feature for r in out][:3] == [
        "median_cashout_latency_min", "unique_buyers_24h", "account_age_days"
    ]  # fmt: skip
    assert all(r.direction == "risk" for r in out[:3])
    assert out[0].key == "FAST_CASHOUT" and out[0].text_bn and out[0].text_en


def test_trusted_seller_sees_protective_reasons_first() -> None:
    values, contrib, medians = _values_and_contrib()
    out = rs.build_reasons(values, contrib, medians, score=90)
    assert out[0].direction == "protective" and out[0].feature == "refund_rate"


def test_limited_history_reason_comes_first_and_missing_values_are_skipped() -> None:
    values, contrib, medians = _values_and_contrib()
    values["median_cashout_latency_min"] = float("nan")
    out = rs.build_reasons(values, contrib, medians, score=50, limited_history=True)
    assert out[0].key == "LIMITED_HISTORY" and out[0].direction == "neutral"
    assert len(out) <= 4
    assert "median_cashout_latency_min" not in [r.feature for r in out]


def test_generic_wording_is_used_when_no_specific_reason_exists() -> None:
    assert rs.select_key("repeat_buyer_ratio", "protective", "low") == "GENERIC_PROTECTIVE"
    assert rs.select_key("orders_7d", "protective", "low") == "NO_ORDER_RUSH_7D"


# ---- the model --------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def trained():
    cfg = load_config()
    data = gs.generate("v1", cfg, n_sellers=900)
    features = compute_features(
        data.sellers, data.orders, data.daily_stats, data.params["categories"],
        data.params["as_of"], cfg,
    )  # fmt: skip
    sellers = data.sellers.set_index("id")
    model, report = train_model(features, sellers.loc[features.index, "is_high_risk"], cfg)
    return model, report, features, sellers


def _predict(model: TrustModel, features: pd.DataFrame, seller_id: str):
    row = features.loc[seller_id]
    values = {c: (None if pd.isna(row[c]) else float(row[c])) for c in model.feature_columns}
    return model.predict(values, seller_id=seller_id, order_count=int(row["orders_total"]))


def test_splits_are_disjoint_and_cover_everything(trained) -> None:
    _, report, features, _ = trained
    ids = report["split_seller_ids"]
    parts = [set(v) for v in ids.values()]
    assert sum(len(p) for p in parts) == len(features)
    assert not (parts[0] & parts[1]) and not (parts[0] & parts[2]) and not (parts[1] & parts[2])
    sizes = {k: len(v) for k, v in ids.items()}
    assert sizes["train"] > sizes["validation"] and sizes["validation"] == sizes["calibration"]


def test_response_follows_the_contract(trained) -> None:
    model, _, features, _ = trained
    api = _predict(model, features, features.index[0]).to_api()
    assert set(api) == {
        "seller_id", "score", "band", "limited_history", "reasons", "model_version", "generated_at",
    }  # fmt: skip
    assert api["generated_at"].endswith("Z") and api["model_version"] == "trust_v1"
    assert 2 <= len(api["reasons"]) <= 4
    assert all(set(r) == {"key", "direction", "text_en", "text_bn"} for r in api["reasons"])


def test_every_seller_gets_two_to_four_reasons(trained) -> None:
    model, _, features, _ = trained
    counts = {len(_predict(model, features, sid).reasons) for sid in features.index[:300]}
    assert counts <= {2, 3, 4}


def test_fake_sellers_are_flagged_and_established_ones_trusted(trained) -> None:
    model, _, features, sellers = trained
    fake = [s for s in features.index if sellers.loc[s, "archetype"] == "fake_burst"]
    solid = [s for s in features.index if sellers.loc[s, "archetype"] == "honest_established"]
    bands_fake = [_predict(model, features, s).band for s in fake]
    bands_solid = [_predict(model, features, s).band for s in solid[:150]]
    assert np.mean([b == TrustBand.HIGH_RISK for b in bands_fake]) >= 0.9
    assert np.mean([b == TrustBand.TRUSTED for b in bands_solid]) >= 0.9


def test_limited_history_hides_the_score_but_explains_why(trained) -> None:
    model, _, features, sellers = trained
    new = [
        s for s in features.index
        if sellers.loc[s, "archetype"] == "honest_new" and features.loc[s, "account_age_days"] < 14
    ]  # fmt: skip
    result = next(r for r in (_predict(model, features, s) for s in new) if r.limited_history)
    api = result.to_api()
    assert result.band == TrustBand.LIMITED_HISTORY and api["score"] is None
    assert api["limited_history"] is True and api["reasons"][0]["key"] == "LIMITED_HISTORY"
    assert result.model_score is not None  # still stored internally for the snapshot


def test_probabilities_are_valid_and_calibrated_in_range(trained) -> None:
    model, _, features, _ = trained
    p = model.predict_proba(features)
    assert ((p >= 0) & (p <= 1)).all() and p.std() > 0.1


def test_save_and_load_round_trip(trained, tmp_path) -> None:
    model, _, features, _ = trained
    model.save(tmp_path / "m.joblib")
    loaded = TrustModel.load(tmp_path / "m.joblib")
    assert np.allclose(model.predict_proba(features), loaded.predict_proba(features))
    assert loaded.version == model.version and loaded.medians == model.medians


def test_training_is_deterministic(trained) -> None:
    model, _, features, sellers = trained
    again, _ = train_model(features, sellers.loc[features.index, "is_high_risk"])
    assert np.allclose(model.predict_proba(features), again.predict_proba(features))


def test_inference_is_fast(trained) -> None:
    import time

    model, _, features, _ = trained
    _predict(model, features, features.index[0])  # warm-up
    start = time.perf_counter()
    for sid in features.index[:50]:
        _predict(model, features, sid)
    per_call_ms = (time.perf_counter() - start) / 50 * 1000
    assert per_call_ms < load_config()["trust_model"]["latency_budget_ms"]


def test_split_indices_are_stratified() -> None:
    labels = pd.Series([0] * 80 + [1] * 20)
    parts = split_indices(labels, {"train": 0.6, "validation": 0.2, "calibration": 0.2}, seed=1)
    for idx in parts.values():
        assert labels.iloc[idx].mean() == pytest.approx(0.2, abs=0.05)


def test_clock_is_used_for_the_timestamp(trained) -> None:
    model, _, features, _ = trained
    fixed = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    row = features.iloc[0]
    values = {c: (None if pd.isna(row[c]) else float(row[c])) for c in model.feature_columns}
    result = model.predict(values, generated_at=SimClock(fixed).now())
    assert result.to_api()["generated_at"] == "2026-10-01T09:00:00Z"
    assert json.dumps(result.to_api())  # JSON serialisable


# ---- database loading -------------------------------------------------------------------------


def test_features_are_loaded_into_the_database(tmp_path, trained) -> None:
    _, _, features, _ = trained
    data = gs.generate("v1", n_sellers=900)
    engine = make_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    create_db(engine)
    gs.load_into_db(data, engine, features)
    with Session(engine) as session:
        assert session.exec(select(func.count()).select_from(SellerFeatures)).one() == len(features)
        first = session.get(SellerFeatures, features.index[0])
        assert first.orders_total == features.iloc[0]["orders_total"]


def test_generic_wording_carries_units() -> None:
    assert "30%" in rs.render("GENERIC_RISK", "dispute_rate", 0.3, "en")
    assert "৩০%" in rs.render("GENERIC_RISK", "dispute_rate", 0.3, "bn")
    assert "778 days" in rs.render("GENERIC_RISK", "account_age_days", 778, "en")


def test_more_refunds_and_disputes_never_make_a_seller_look_safer(trained) -> None:
    model, _, features, _ = trained
    worse = features.copy()
    worse["orders_total"] += 1
    worse["refund_count"] += 1
    worse["dispute_count"] += 1
    worse["refund_rate"] = worse["refund_count"] / worse["orders_total"]
    worse["dispute_rate"] = worse["dispute_count"] / worse["orders_total"]
    before = model.predict_proba(features)
    assert (model.predict_proba(worse) >= before - 1e-12).all()
    # and the same for a larger step on each rate separately
    for column in ("refund_rate", "dispute_rate"):
        bumped = features.assign(**{column: features[column] + 0.2})
        assert (model.predict_proba(bumped) >= before - 1e-12).all(), column


def test_unknown_monotone_feature_is_rejected(trained) -> None:
    _, _, features, sellers = trained
    cfg = load_config()
    cfg = {
        **cfg,
        "trust_model": {**cfg["trust_model"], "monotone_increasing_risk": ["not_a_feature"]},
    }
    with pytest.raises(ValueError):
        train_model(features, sellers.loc[features.index, "is_high_risk"], cfg)


def test_validation_arguments_fit_old_and_new_lightgbm() -> None:
    from app.trust.model import eval_kwargs

    def new_fit(X, y, *, eval_X=None, eval_y=None):  # noqa: N803  (mirrors LightGBM's names)
        return None

    def old_fit(X, y, *, eval_set=None):  # noqa: N803
        return None

    assert eval_kwargs(new_fit, "x", "y") == {"eval_X": "x", "eval_y": "y"}
    assert eval_kwargs(old_fit, "x", "y") == {"eval_set": [("x", "y")]}
