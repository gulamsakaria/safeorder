"""Prompt-injection checks for the evidence analyzer (BLUEPRINT.md Sections 9.3 and 10).

Usage: PYTHONPATH=backend:. python -m eval.injection_eval   -> reports/injection_eval.json

Two kinds of numbers, and they mean different things:

* **Screen detection** on the developer-written phrases in ``eval/injection_samples.py``. The
  patterns were written while looking at these phrases, so this is a regression check, NOT an
  estimate of detection on attacks nobody has seen. The team's own held-out injection set (Step 5)
  is not available yet, and the report says so.
* **Invariance**: for every detected phrase, appended to the buyer's or the seller's evidence of
  four base cases, the classifier must see exactly the same text, and the probabilities,
  recommendation and flags must stay as they were, except for the injection flag and a forced
  human review. A fixed stand-in classifier is used so only the analyzer logic is under test.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.analyzer.case import DisputeCase
from app.analyzer.pipeline import analyze_case
from app.config import load_config
from app.disputes import classifier as clf
from app.disputes.injection import scan
from app.enums import DisputeClass, FlagCode, Route
from app.trust.dataset import REPO_ROOT
from eval.injection_samples import HARMLESS, INJECTIONS, UNTUNED_INJECTIONS

T0 = datetime(2026, 9, 28, 9, 10, tzinfo=UTC)
HOUR = timedelta(hours=1)
CLASSIFIER_P = 0.9


class FixedClassifier:
    version = "fixed_eval_v0"

    def __init__(self, top: str, p: float) -> None:
        rest = (1.0 - p) / (len(clf.CLASSES) - 1)
        self.probs = {c: (p if c == top else rest) for c in clf.CLASSES}
        self.seen: list[str] = []

    def predict_proba(self, text: str) -> dict[str, float]:
        self.seen.append(text)
        return dict(self.probs)


def _case(**overrides: Any) -> DisputeCase:
    base: dict[str, Any] = {
        "dispute_id": "D-EVAL", "order_id": "O-EVAL", "amount_bdt": 1500, "placed_at": T0,
        "opened_at": T0 + 40 * HOUR,
        "claim_text": "The box arrived crushed and the item inside is cracked.",
        "courier_events": [("in_transit", T0 + 6 * HOUR), ("delivered", T0 + 30 * HOUR)],
        "seller_response_text": "I packed it properly with bubble wrap before handing it over.",
        "seller_responded_at": T0 + 42 * HOUR,
        "buyer_evidence": [
            "Photo shows the box was crushed at the corner and the item is cracked."
        ],
        "seller_evidence": ["Courier tracking number is attached and the packing photo is clear."],
    }  # fmt: skip
    base.update(overrides)
    return DisputeCase(**base)


BASE_CASES: dict[str, tuple[DisputeCase, str]] = {
    "fast_lane_courier_damage": (_case(), DisputeClass.COURIER_ISSUE),
    "false_claim_with_code": (
        _case(
            claim_text="I did not receive the parcel at all.",
            courier_events=[("delivered", T0 + 30 * HOUR)],
            code_confirmed_at=T0 + 30.1 * HOUR,
            buyer_disputes_in_window=3,
        ),
        DisputeClass.BUYER_FALSE_CLAIM,
    ),
    "never_dispatched": (
        _case(
            courier_events=[],
            seller_response_text="I will send it soon.",
            seller_evidence=["I will send it this week, please wait for the parcel."],
        ),
        DisputeClass.SELLER_FAULT,
    ),
    "high_amount": (_case(amount_bdt=8000), DisputeClass.SELLER_FAULT),
}


def _with_text(case: DisputeCase, side: str, text: str) -> DisputeCase:
    field = "buyer_evidence" if side == "buyer" else "seller_evidence"
    original = list(getattr(case, field))
    original[0] = f"{original[0]} {text}"
    return DisputeCase(**{**case.__dict__, field: original})


def invariance(cfg: dict[str, Any]) -> dict[str, Any]:
    missed_phrases = [p for p in INJECTIONS if not scan(p)]
    counts = {
        "pairs_checked": 0, "classifier_text_changed": 0, "probabilities_changed": 0,
        "recommendation_changed": 0, "flags_changed_beyond_injection_flag": 0,
        "human_review_not_forced": 0,
    }  # fmt: skip
    leaked_when_missed = 0
    for case, top in BASE_CASES.values():
        plain_clf = FixedClassifier(top, CLASSIFIER_P)
        plain = analyze_case(case, plain_clf, cfg)
        for side in ("buyer", "seller"):
            for phrase in INJECTIONS:
                injected_clf = FixedClassifier(top, CLASSIFIER_P)
                result = analyze_case(_with_text(case, side, phrase), injected_clf, cfg)
                if phrase in missed_phrases:
                    leaked_when_missed += int(injected_clf.seen != plain_clf.seen)
                    continue
                counts["pairs_checked"] += 1
                counts["classifier_text_changed"] += int(injected_clf.seen != plain_clf.seen)
                counts["probabilities_changed"] += int(result.class_probs != plain.class_probs)
                counts["recommendation_changed"] += int(
                    result.recommendation != plain.recommendation
                )
                others = [f for f in result.flags if f != FlagCode.INJECTION_DETECTED]
                counts["flags_changed_beyond_injection_flag"] += int(others != plain.flags)
                counts["human_review_not_forced"] += int(result.route != Route.HUMAN_REVIEW)
    return {
        **counts,
        "phrases_not_detected": missed_phrases,
        "text_reached_classifier_when_not_detected": leaked_when_missed,
    }


def main() -> None:
    cfg = load_config()
    detected = [p for p in INJECTIONS if scan(p)]
    false_alarms = [p for p in HARMLESS if scan(p)]
    untuned_missed = [p for p in UNTUNED_INJECTIONS if not scan(p)]
    report = {
        "note": (
            "Developer-written phrases. The screen's patterns were written while looking at them, "
            "so detection here is a regression check, not an estimate on unseen attacks. The "
            "team's held-out injection set is not measured yet (needs Step 5 cases)."
        ),
        "held_out_set": "not_measured",
        "screen": {
            "injection_phrases": len(INJECTIONS),
            "detected": len(detected),
            "detection_rate": len(detected) / len(INJECTIONS),
            "harmless_phrases": len(HARMLESS),
            "false_alarms": len(false_alarms),
            "false_alarm_rate": len(false_alarms) / len(HARMLESS),
        },
        "untuned_screen": {
            "note": (
                "Phrases written after the screen was finished and never used to change it. "
                "Developer-written and small: an indication of reach, not an estimate. A phrase "
                "the screen misses reaches the classifier as ordinary text; the trained classifier "
                "(Step 6) must be checked on the team's own injection set."
            ),
            "phrases": len(UNTUNED_INJECTIONS),
            "detected": len(UNTUNED_INJECTIONS) - len(untuned_missed),
            "detection_rate": 1 - len(untuned_missed) / len(UNTUNED_INJECTIONS),
            "not_detected": untuned_missed,
        },
        "invariance": invariance(cfg),
        "base_cases": sorted(BASE_CASES),
    }
    path = REPO_ROOT / cfg["paths"]["reports_dir"] / "injection_eval.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    print(json.dumps(report["screen"], indent=2))
    print(json.dumps(report["invariance"], indent=2, ensure_ascii=False))
    print(f"wrote {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
