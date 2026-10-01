"""Rehearse the demo script (BLUEPRINT.md Section 12.2) from a clean reset, several times.

Usage (repository root): PYTHONPATH=backend:. python -m scripts.demo_rehearsal [--runs 3]
Needs `make data` and `make train`. Every run uses a fresh database and a reset clock, loads the
demo scenarios through POST /api/demo/reset, plays scenarios 1 to 6 through the real API, and
checks the end state. The runs must give identical results. Exit status 1 on any failure.

**Stand-in classifier:** the dispute classifier is not trained yet (Step 6), so the analyzer runs
with a fixed stand-in that always answers the same probabilities. It only lets the rule-based
parts (flags, routing, injection screen, ledger, trust feedback) be rehearsed; it says nothing about
classification quality. Scenario 7 (judge case) needs the real classifier and is not rehearsed.
"""

import argparse
import copy
import sys
import tempfile
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.clock import clock
from app.config import load_config
from app.db import create_db, make_engine
from app.disputes import classifier as clf
from app.enums import DisputeClass
from app.main import create_app
from app.trust.model import TrustModel

REPO = Path(__file__).resolve().parents[1]


class StandInClassifier:
    version = "stand_in_rehearsal"

    def __init__(self) -> None:
        top, rest = DisputeClass.SELLER_FAULT.value, 0.1 / (len(clf.CLASSES) - 1)
        self.probs = {c: (0.9 if c == top else rest) for c in clf.CLASSES}

    def predict_proba(self, text: str) -> dict[str, float]:
        return dict(self.probs)


class RehearsalError(AssertionError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RehearsalError(message)


def run_once(directory: Path) -> dict[str, Any]:
    cfg = copy.deepcopy(load_config())
    cfg["api"]["rate_limit_per_minute"] = 0  # a rehearsal is fast; the limit has its own tests
    clock.reset()
    engine = make_engine(f"sqlite:///{directory / 'rehearsal.db'}")
    create_db(engine)
    model = TrustModel.load(
        REPO / cfg["paths"]["models_dir"] / f"{cfg['trust_model']['version']}.joblib"
    )
    client = TestClient(create_app(engine, model, StandInClassifier(), cfg))

    def call(method: str, path: str, body: dict | None = None) -> dict[str, Any]:
        response = client.request(method, f"/api{path}", json=body)
        check(
            response.status_code < 300,
            f"{method} {path}: {response.status_code} {response.text[:200]}",
        )
        return response.json()

    reset = call("POST", "/demo/reset", {"scenario_set": "demo"})
    s = {item["key"]: item for item in reset["scenarios"]}
    check(len(s) == 7, "expected seven scenarios")
    result: dict[str, Any] = {"loaded": reset["loaded"]}

    fake = call("POST", "/trust/check", {"seller_id": s["fake_seller"]["seller_id"]})
    check(
        fake["band"] == "HIGH_RISK" and fake["requires_extra_confirmation"],
        "1: fake seller not HIGH_RISK",
    )
    result["1"] = [fake["band"], fake["score"], [r["key"] for r in fake["reasons"]]]

    happy = s["happy_path"]
    held = call("GET", f"/orders/{happy['order_id']}")
    check(held["status"] == "HELD", "2: order should be held")
    call("POST", f"/orders/{happy['order_id']}/confirm-delivery", {"code": happy["delivery_code"]})
    call("POST", "/sim/advance-clock", {"hours": 72})
    done = call("GET", f"/orders/{happy['order_id']}")
    check(
        done["status"] == "RELEASED" and done["ledger_balanced"],
        "2: hold not released or books unbalanced",
    )
    result["2"] = [done["status"], done["ledger_balanced"]]

    fault = s["seller_fault"]
    case = call("GET", f"/analyst/disputes/{fault['dispute_id']}")
    check(case["analysis"] is not None, "3: dispute should be analysed")
    decision = call(
        "POST", f"/analyst/disputes/{fault['dispute_id']}/decision",
        {"decision": "REFUND_BUYER", "note": "rehearsal: seller never shipped", "analyst_id": "r"},
    )  # fmt: skip
    trust = decision["trust"]
    check(
        decision["order_status"] == "REFUNDED" and decision["ledger_balanced"],
        "3: refund not booked",
    )
    check(trust["after"]["score"] < trust["before"]["score"], "3: score did not drop")
    result["3"] = [decision["order_status"], trust["before"]["score"], trust["after"]["score"]]

    false_claim = s["false_claim"]
    analysis = call("GET", f"/analyst/disputes/{false_claim['dispute_id']}")["analysis"]
    check({"CODE_CONTRADICTION", "REPEAT_CLAIMANT"} <= set(analysis["flags"]), "4: flags missing")
    check(analysis["route"] == "HUMAN_REVIEW", "4: must go to a human")
    rejected = call(
        "POST", f"/analyst/disputes/{false_claim['dispute_id']}/decision",
        {"decision": "REJECT_CLAIM", "note": "rehearsal: code used", "analyst_id": "rehearsal"},
    )  # fmt: skip
    check(rejected["order_status"] == "RELEASED", "4: claim not rejected")
    result["4"] = [analysis["flags"], analysis["route"], rejected["order_status"]]

    new = call("POST", "/trust/check", {"seller_id": s["honest_new"]["seller_id"]})
    check(new["band"] == "LIMITED_HISTORY" and new["score"] is None, "5: should be LIMITED_HISTORY")
    result["5"] = [new["band"], new["score"]]

    injection = call("GET", f"/analyst/disputes/{s['injection']['dispute_id']}")["analysis"]
    check(
        injection["injection_detected"] and injection["route"] == "HUMAN_REVIEW",
        "6: injection not handled",
    )
    result["6"] = [injection["flags"], injection["route"]]

    queue = call("GET", "/analyst/queue")
    result["queue"] = sorted(item["dispute_id"] for item in queue)
    check(len(queue) == 1, "only the injection case should still wait")
    clock.reset()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    print("NOTE: stand-in classifier (not a trained model); scenario 7 is not rehearsed.")
    results = []
    for number in range(1, args.runs + 1):
        with tempfile.TemporaryDirectory() as tmp:
            try:
                results.append(run_once(Path(tmp)))
            except (RehearsalError, FileNotFoundError) as error:
                print(f"run {number}: FAILED: {error}")
                return 1
        print(f"run {number}: scenarios 1-6 passed")
    if any(r != results[0] for r in results[1:]):
        print("FAILED: the runs did not give identical results")
        return 1
    print(f"{args.runs} clean runs, identical results")
    return 0


if __name__ == "__main__":
    sys.exit(main())
