"""Recommendation and routing (BLUEPRINT.md Section 6.2). Pure rules on top of model output.

A suggestion never moves money. Anything unusual goes to a human; the fast lane only offers a
one-click confirmation that the analyst still has to make.
"""

from dataclasses import dataclass
from typing import Any

from app.config import load_config
from app.disputes.classifier import top_class
from app.enums import DisputeClass, FlagCode, Recommendation, Route

RECOMMENDATIONS: dict[str, Recommendation] = {
    DisputeClass.SELLER_FAULT: Recommendation.SUGGEST_REFUND_BUYER,
    DisputeClass.BUYER_FALSE_CLAIM: Recommendation.SUGGEST_REJECT_CLAIM,
    DisputeClass.COURIER_ISSUE: Recommendation.SUGGEST_COURIER_ISSUE,
    DisputeClass.INSUFFICIENT_EVIDENCE: Recommendation.NEEDS_MORE_EVIDENCE,
}

FLAGS_PRESENT = "FLAGS_PRESENT"
INSUFFICIENT_EVIDENCE_PREDICTED = "INSUFFICIENT_EVIDENCE_PREDICTED"
LOW_CONFIDENCE = "LOW_CONFIDENCE"
HIGH_AMOUNT = "HIGH_AMOUNT"
INJECTION_DETECTED = FlagCode.INJECTION_DETECTED.value


@dataclass(frozen=True)
class Routing:
    top_class: str
    top_probability: float
    recommendation: Recommendation
    route: Route
    route_reasons: list[str]


def decide_route(
    probs: dict[str, float],
    amount_bdt: int,
    consistency_flags: list[str],
    injection_detected: bool,
    cfg: dict[str, Any] | None = None,
) -> Routing:
    """Apply the routing table. ``consistency_flags`` excludes the injection flag."""
    routing = (cfg or load_config())["rules"]["routing"]
    best, probability = top_class(probs)

    reasons: list[str] = []
    if best in routing["always_human_classes"]:
        reasons.append(INSUFFICIENT_EVIDENCE_PREDICTED)
    if consistency_flags:
        reasons.append(FLAGS_PRESENT)
    if injection_detected:
        reasons.append(INJECTION_DETECTED)
    if probability < routing["min_class_probability"]:
        reasons.append(LOW_CONFIDENCE)
    if amount_bdt > routing["high_amount_bdt"]:
        reasons.append(HIGH_AMOUNT)

    return Routing(
        top_class=best,
        top_probability=probability,
        recommendation=RECOMMENDATIONS[best],
        route=Route.HUMAN_REVIEW if reasons else Route.FAST_LANE_CONFIRM,
        route_reasons=reasons,
    )
