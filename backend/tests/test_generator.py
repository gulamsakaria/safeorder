import json
import re

import pytest
from sqlmodel import Session, func, select

from app.config import load_config
from app.db import create_db, make_engine
from app.models import Buyer, Seller, SellerDailyStats
from scripts import generate_sellers as gs

N = 800
SHARE_TOLERANCE = 0.02


@pytest.fixture(scope="module")
def v1() -> gs.GeneratedData:
    return gs.generate("v1", n_sellers=N)


@pytest.fixture(scope="module")
def v2() -> gs.GeneratedData:
    return gs.generate("v2", n_sellers=N)


def _shares(data: gs.GeneratedData) -> dict[str, float]:
    return (data.sellers["archetype"].value_counts() / len(data.sellers)).to_dict()


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_archetype_shares_match_config(version: str, v1, v2) -> None:
    data = {"v1": v1, "v2": v2}[version]
    expected = data.params["shares"]
    realised = _shares(data)
    assert set(realised) == set(expected)
    for archetype, share in expected.items():
        assert abs(realised[archetype] - share) <= SHARE_TOLERANCE, archetype


def test_default_shares_are_the_blueprint_mix() -> None:
    shares = load_config()["generator"]["shares"]
    assert shares == {
        "honest_established": 0.55, "honest_new": 0.15, "fake_burst": 0.12,
        "slow_scammer": 0.08, "collusive_ring": 0.05, "chronic_poor_service": 0.05,
    }  # fmt: skip


def test_archetype_counts_add_up() -> None:
    shares = {"a": 0.55, "b": 0.15, "c": 0.3}
    for n in (1, 7, 100, 3001):
        assert sum(gs.archetype_counts(shares, n).values()) == n


def test_same_seed_gives_identical_files(tmp_path, v1) -> None:
    first = gs.write_outputs(v1, tmp_path / "a")
    second = gs.write_outputs(gs.generate("v1", n_sellers=N), tmp_path / "b")
    assert first == second
    assert all(info["sha256"] for info in first["files"].values())


def test_versions_use_different_seeds(tmp_path, v1, v2) -> None:
    a = gs.write_outputs(v1, tmp_path / "a")["files"]["orders.csv"]["sha256"]
    b = gs.write_outputs(v2, tmp_path / "b")["files"]["orders.csv"]["sha256"]
    assert a != b


def test_v2_distributions_differ_measurably_from_v1(v1, v2) -> None:
    s1, s2 = gs.summarize(v1)["per_archetype"], gs.summarize(v2)["per_archetype"]
    assert _shares(v1)["honest_new"] < _shares(v2)["honest_new"]
    assert s2["fake_burst"]["mean_ticket_ratio"] < 0.9 * s1["fake_burst"]["mean_ticket_ratio"]
    assert s2["fake_burst"]["unique_buyers_24h"] < 0.95 * s1["fake_burst"]["unique_buyers_24h"]
    assert s2["honest_established"]["orders"] < 0.9 * s1["honest_established"]["orders"]
    assert s2["collusive_ring"]["repeat_buyer_ratio"] < s1["collusive_ring"]["repeat_buyer_ratio"]


def test_archetype_signatures(v1) -> None:
    stats = gs.summarize(v1)["per_archetype"]
    fake, honest = stats["fake_burst"], stats["honest_established"]
    assert fake["median_cashout_min"] < 0.1 * honest["median_cashout_min"]
    assert fake["repeat_buyer_ratio"] < 0.1 < honest["repeat_buyer_ratio"]
    assert fake["unique_buyers_24h"] > 10 * honest["unique_buyers_24h"]
    assert stats["chronic_poor_service"]["dispute_rate"] > 5 * honest["dispute_rate"]
    assert stats["collusive_ring"]["unique_buyers"] < honest["unique_buyers"]
    assert 0.25 <= honest["repeat_buyer_ratio"] <= 0.60  # blueprint: 25-60%


def test_label_rule_and_noise(v1) -> None:
    sellers = v1.sellers
    clean = sellers["archetype"].isin(gs.HIGH_RISK_ARCHETYPES).astype(int)
    assert ((clean != sellers["is_high_risk"]).astype(int) == sellers["label_noised"]).all()
    assert 0.02 <= sellers["label_noised"].mean() <= 0.07  # configured 4%


def test_overlap_makes_the_task_not_trivial(v1) -> None:
    sellers, orders = v1.sellers, v1.orders
    fast = orders.groupby("seller_id")["cashout_latency_min"].median()
    new = sellers[sellers["archetype"] == "honest_new"]["id"]
    assert (fast.loc[new] < 100).any()  # some honest new sellers cash out as fast as scammers


def test_daily_stats_are_consistent_with_orders(v1) -> None:
    stats, orders, sellers = v1.daily_stats, v1.orders, v1.sellers
    assert stats["orders"].sum() == len(orders)
    assert stats["inflow_bdt"].sum() == orders["amount_bdt"].sum()
    assert stats["refunds"].sum() == orders["refunded"].sum()
    assert (stats["unique_buyers"] <= stats["orders"]).all()
    rows = stats.groupby("seller_id").size()
    assert (rows.loc[sellers["id"]].to_numpy() == sellers["stats_days"].to_numpy()).all()
    lo, hi = v1.params["stats_window_days"]
    age = sellers["account_age_days"]
    assert (sellers["stats_days"] <= age.clip(upper=hi)).all()
    assert (sellers["stats_days"] >= age.clip(upper=lo)).all()


def test_all_orders_happen_before_the_scoring_moment(v1) -> None:
    assert (v1.orders["placed_at"] < v1.params["as_of"]).all()
    assert (v1.orders["amount_bdt"] >= v1.params["min_amount_bdt"]).all()


PHONE_LIKE = re.compile(r"(?:\+?88)?01[3-9]\d{8}|\d{8,}")


def test_no_real_looking_phone_numbers_or_names(v1, v2) -> None:
    for data in (v1, v2):
        for frame in (data.sellers, data.buyers, data.orders):
            for column in frame.columns:
                assert not frame[column].astype(str).str.contains(PHONE_LIKE).any(), column
        assert data.sellers["display_name"].str.fullmatch(r"Synthetic Shop \d{4}").all()
        assert data.buyers["display_name"].str.fullmatch(r"Synthetic Buyer \d{6}").all()
        assert data.sellers["wallet_no"].str.fullmatch(r"SIM-W-S\d{4}").all()
        assert data.buyers["wallet_no"].str.fullmatch(r"SIM-W-B\d{6}").all()


def test_apply_scale() -> None:
    out = gs.apply_scale({"x": {"n": [10, 20], "p": 0.5, "k": 4}}, {"x.n": 0.8, "x.p": 1.2})
    assert out["x"] == {"n": [8, 16], "p": 0.6, "k": 4}


def test_unknown_version_is_rejected() -> None:
    with pytest.raises(ValueError):
        gs.build_params("v3")


def test_load_into_database(tmp_path, v1) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    create_db(engine)
    gs.load_into_db(v1, engine)
    with Session(engine) as session:
        assert session.exec(select(func.count()).select_from(Seller)).one() == len(v1.sellers)
        assert session.exec(select(func.count()).select_from(Buyer)).one() == len(v1.buyers)
        total = session.exec(select(func.count()).select_from(SellerDailyStats)).one()
        assert total == len(v1.daily_stats)
        seller = session.get(Seller, "S-0001")
        assert seller.archetype is not None  # ground truth stays in the database only


def test_assumptions_doc_is_generated(tmp_path, v1) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "synthetic_summary_v1.json").write_text(json.dumps(gs.summarize(v1)))
    doc = tmp_path / "synthetic_assumptions.md"
    gs.write_assumptions_doc(doc, reports)
    text = doc.read_text()
    assert "not validated on real data" in text
    assert "fake_burst" in text and "Realised statistics, v1" in text
