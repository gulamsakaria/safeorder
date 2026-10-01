"""The demo scenarios (BLUEPRINT.md Section 12.2) are set up through the API as scripted."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.clock import clock
from app.config import load_config
from app.db import create_db, make_engine
from app.demo_scenarios import load_demo_scenarios
from app.enums import DisputeClass, DisputeStatus, TrustBand
from app.main import create_app
from app.models import Dispute
from app.seed import SCENARIO_SETS, load_synthetic
from app.trust.features import compute_features
from app.trust.model import TrustModel
from app.trust.service import check_seller
from scripts import generate_sellers as gs
from tests.test_analyzer import FixedClassifier

REPO = Path(__file__).resolve().parents[2]
N_SELLERS = 3000


@pytest.fixture(scope="module")
def source():
    clock.reset()
    cfg = load_config()
    data = gs.generate("v1", n_sellers=N_SELLERS)
    features = compute_features(
        data.sellers, data.orders, data.daily_stats, cfg["generator"]["categories"],
        cfg["generator"]["as_of"], cfg,
    )  # fmt: skip
    model = TrustModel.load(REPO / "models" / "trust_v1.joblib")
    return cfg, data, features, model


def build(source, directory: Path):
    """A fresh database with the generated data and the demo scenarios loaded."""
    clock.reset()
    cfg, data, features, model = source
    engine = make_engine(f"sqlite:///{directory / 'demo.db'}")
    create_db(engine)
    load_synthetic(
        engine, data.sellers, data.buyers, data.daily_stats, features, cfg["generator"]["as_of"]
    )
    classifier = FixedClassifier(DisputeClass.SELLER_FAULT.value, 0.9)
    scenarios = {s["key"]: s for s in load_demo_scenarios(engine, model, classifier, cfg)}
    client = TestClient(create_app(engine, model, classifier, cfg))
    return engine, model, cfg, scenarios, client


@pytest.fixture(scope="module")
def world(source, tmp_path_factory):
    yield build(source, tmp_path_factory.mktemp("demo"))
    clock.reset()


def get(client, path):
    response = client.get(f"/api{path}")
    assert response.status_code == 200, response.text
    return response.json()


def trust_of(world, key):
    engine, model, cfg, scenarios, _ = world
    with Session(engine) as session:
        return check_seller(session, model, seller_id=scenarios[key]["seller_id"], cfg=cfg)


def analysis_of(world, key):
    client, scenarios = world[4], world[3]
    return get(client, f"/analyst/disputes/{scenarios[key]['dispute_id']}")["analysis"]


def test_all_seven_scenarios_are_present_in_order(world) -> None:
    scenarios = world[3]
    assert [s["number"] for s in scenarios.values()] == [1, 2, 3, 4, 5, 6, 7]
    assert "demo" in SCENARIO_SETS


def test_fake_seller_is_high_risk_with_a_burst(world) -> None:
    result = trust_of(world, "fake_seller")
    assert result.band == TrustBand.HIGH_RISK
    assert len(result.reasons) >= 2


def test_honest_seller_is_trusted_and_the_order_is_held(world) -> None:
    client, scenarios = world[4], world[3]
    assert trust_of(world, "happy_path").band == TrustBand.TRUSTED
    order = get(client, f"/orders/{scenarios['happy_path']['order_id']}")
    assert order["status"] == "HELD"
    assert scenarios["happy_path"]["delivery_code"]


def test_honest_new_seller_is_limited_history_not_high_risk(world) -> None:
    result = trust_of(world, "honest_new")
    assert result.band == TrustBand.LIMITED_HISTORY
    assert result.score is None


def test_seller_fault_refund_drops_the_score(source, tmp_path) -> None:
    fresh = build(source, tmp_path)
    client, scenarios = fresh[4], fresh[3]
    case = get(client, f"/analyst/disputes/{scenarios['seller_fault']['dispute_id']}")
    assert case["dispute"]["status"] == "ANALYZED"
    assert case["analysis"] is not None
    before = trust_of(fresh, "seller_fault").score
    decision = client.post(
        f"/api/analyst/disputes/{scenarios['seller_fault']['dispute_id']}/decision",
        json={"decision": "REFUND_BUYER", "note": "demo check", "analyst_id": "tester"},
    )
    assert decision.status_code == 200, decision.text
    trust = decision.json()["trust"]
    assert trust["before"]["score"] == before
    assert trust["after"]["score"] < before


def test_false_claim_flags_the_contradiction_and_the_repeat_claimant(world) -> None:
    analysis = analysis_of(world, "false_claim")
    assert "CODE_CONTRADICTION" in analysis["flags"]
    assert "REPEAT_CLAIMANT" in analysis["flags"]
    assert analysis["route"] == "HUMAN_REVIEW"


def test_only_the_three_dispute_scenarios_wait_in_the_queue(world) -> None:
    engine, _, _, scenarios, client = world
    queued = {item["dispute_id"] for item in get(client, "/analyst/queue")}
    expected = {scenarios[k]["dispute_id"] for k in ("seller_fault", "false_claim", "injection")}
    assert queued == expected
    with Session(engine) as session:
        resolved = session.exec(
            select(Dispute).where(Dispute.status == DisputeStatus.RESOLVED)
        ).all()
    assert len(resolved) == 2  # the buyer's two earlier claims, rejected by the seed analyst


def test_injection_sets_the_flag_and_forces_human_review(world) -> None:
    analysis = analysis_of(world, "injection")
    assert analysis["injection_detected"] is True
    assert analysis["route"] == "HUMAN_REVIEW"


def test_demo_set_is_deterministic(source, tmp_path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    first = build(source, tmp_path / "a")[3]
    second = build(source, tmp_path / "b")[3]
    assert first == second
