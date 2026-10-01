"""The evidence analyzer: one call from a dispute to a structured, explainable recommendation.

Order of work (BLUEPRINT.md Section 9.3): injection screen, consistency checks, timeline,
classifier, router, explanation. Rules and templates decide everything except the class
probabilities, which come from the classifier and only ever suggest. A generative model is
never in this path.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session

from app.analyzer import consistency, explain, router, timeline
from app.analyzer.case import DisputeCase, load_case
from app.clock import clock
from app.config import load_config
from app.db import write_audit
from app.disputes.classifier import DisputeClassifier, validate_probabilities
from app.disputes.injection import sanitize
from app.disputes.text_format import build_text
from app.enums import FlagCode
from app.models import AnalysisResult as AnalysisRecord


@dataclass
class Analysis:
    dispute_id: str
    order_id: str
    timeline: list[dict[str, Any]]
    class_probs: dict[str, float]
    flags: list[str]
    injection_detected: bool
    recommendation: str
    route: str
    route_reasons: list[str]
    explanation_en: str
    explanation_bn: str
    explanation_sections: dict[str, dict[str, str]]
    model_versions: dict[str, str]
    flag_details: dict[str, dict[str, Any]] = field(default_factory=dict)
    injection_matches: list[str] = field(default_factory=list)

    def to_api(self) -> dict[str, Any]:
        """Analyzer response (BLUEPRINT.md Section 7) plus the three explanation sections."""
        return {
            "dispute_id": self.dispute_id,
            "order_id": self.order_id,
            "timeline": self.timeline,
            "class_probs": self.class_probs,
            "flags": self.flags,
            "injection_detected": self.injection_detected,
            "recommendation": self.recommendation,
            "route": self.route,
            "route_reasons": self.route_reasons,
            "explanation_en": self.explanation_en,
            "explanation_bn": self.explanation_bn,
            "explanation_sections": self.explanation_sections,
            "model_versions": self.model_versions,
        }

    def to_storage(self) -> dict[str, Any]:
        """Full result for the analysis_result table (matched pattern codes, never the text)."""
        return {
            **self.to_api(),
            "flag_details": self.flag_details,
            "injection_matches": self.injection_matches,
        }


def _screen(case: DisputeCase) -> tuple[consistency.CaseTexts, list[str]]:
    codes: list[str] = []

    def clean(text: str | None) -> str:
        cleaned, found = sanitize(text)
        codes.extend(found)
        return cleaned

    texts = consistency.CaseTexts(
        claim=clean(case.claim_text),
        seller_response=clean(case.seller_response_text),
        buyer_evidence=[clean(t) for t in case.buyer_evidence],
        seller_evidence=[clean(t) for t in case.seller_evidence],
    )
    return texts, sorted(set(codes))


def analyze_case(
    case: DisputeCase, classifier: DisputeClassifier, cfg: dict[str, Any] | None = None
) -> Analysis:
    config = cfg or load_config()
    texts, injection_codes = _screen(case)
    injection_detected = bool(injection_codes)

    flags = consistency.check(case, texts, config)
    classifier_text = build_text(
        courier_status=case.courier_status,
        code_used=case.delivery_code_used,
        amount_bdt=case.amount_bdt,
        buyer_claim=texts.claim,
        seller_response=texts.seller_response,
        buyer_evidence=" ".join(texts.buyer_evidence),
        seller_evidence=" ".join(texts.seller_evidence),
        cfg=config,
    )
    probs = validate_probabilities(classifier.predict_proba(classifier_text))
    routing = router.decide_route(
        probs, case.amount_bdt, [f.code for f in flags], injection_detected, config
    )
    words = explain.explain(case, _with_injection(flags, injection_detected), probs, routing)

    flag_codes = [f.code for f in flags]
    if injection_detected:
        flag_codes.append(FlagCode.INJECTION_DETECTED.value)
    return Analysis(
        dispute_id=case.dispute_id,
        order_id=case.order_id,
        timeline=timeline.build_timeline(case),
        class_probs=probs,
        flags=flag_codes,
        injection_detected=injection_detected,
        recommendation=routing.recommendation.value,
        route=routing.route.value,
        route_reasons=routing.route_reasons,
        explanation_en=words["text"]["en"],
        explanation_bn=words["text"]["bn"],
        explanation_sections=words["sections"],
        model_versions={
            "dispute": classifier.version,
            "rules": config["analyzer"]["rules_version"],
        },
        flag_details={f.code: f.detail for f in flags if f.detail},
        injection_matches=injection_codes,
    )


def _with_injection(flags: list[consistency.Flag], detected: bool) -> list[consistency.Flag]:
    if not detected:
        return flags
    return [*flags, consistency.Flag(FlagCode.INJECTION_DETECTED)]


def analyze(
    session: Session,
    dispute_id: str,
    classifier: DisputeClassifier,
    cfg: dict[str, Any] | None = None,
    persist: bool = True,
) -> Analysis:
    """Analyze a stored dispute and, by default, save the result and an audit-log row."""
    config = cfg or load_config()
    result = analyze_case(load_case(session, dispute_id, config), classifier, config)
    if persist:
        session.add(
            AnalysisRecord(
                dispute_id=dispute_id,
                result_json=json.dumps(result.to_storage(), sort_keys=True, ensure_ascii=False),
                model_versions_json=json.dumps(result.model_versions, sort_keys=True),
                created_at=clock.now(),
            )
        )
        session.flush()
        write_audit(
            session,
            "system",
            "DISPUTE_ANALYZED",
            "dispute",
            dispute_id,
            json.dumps({"route": result.route, "recommendation": result.recommendation}),
        )
    return result
