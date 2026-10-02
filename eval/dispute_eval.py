"""Evaluate the baseline dispute classifier (BLUEPRINT.md Sections 9.2 and 10).

Usage: PYTHONPATH=backend:. python -m eval.dispute_eval   -> reports/dispute_eval_baseline.json

For validation, Test 1 and Test 2 (and each source inside them): macro-F1, accuracy, per-class
precision / recall / F1, the confusion matrix, the wrong-refund and wrong-rejection rates, the
calibration error and log-loss, and the same numbers on one case per distinct story (so repeated
combinations of the same texts do not inflate the score). Then routing through the real analyzer,
the injection set, and the prediction time.

Nothing is tuned on any of these splits; the calibration was fitted on validation, so the
validation numbers are not an honest test and are labelled that way.
"""

import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from app.analyzer.case import DisputeCase
from app.analyzer.pipeline import analyze_case
from app.config import load_config
from app.disputes.baseline import (
    BaselineClassifier,
    case_text,
    expected_calibration_error,
    log_loss,
)
from app.disputes.classifier import CLASSES
from app.disputes.injection import scan
from app.enums import DisputeClass, Route
from app.trust.dataset import REPO_ROOT

REFUND_CLASSES = (DisputeClass.SELLER_FAULT.value, DisputeClass.COURIER_ISSUE.value)
FALSE_CLAIM = DisputeClass.BUYER_FALSE_CLAIM.value
T0 = datetime(2026, 9, 28, 9, 10, tzinfo=UTC)
HOUR = timedelta(hours=1)
MS = 1_000.0
NOTE = (
    "Cases were written by the Claude assistant, not by ChatGPT, Gemini or the team. All splits "
    "share one author, so the scores show that the pipeline works and that wording unseen in "
    "training is handled; they are NOT evidence of how the model would do on cases written by "
    "other people or on real disputes. Test 2 holds few distinct stories (see distinct_stories). "
    "Not validated on real data."
)


def read(name: str, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    path = REPO_ROOT / cfg["dispute"]["cases"]["out_dir"] / f"{name}.jsonl"
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


def rates(true: list[str], pred: list[str]) -> dict[str, Any]:
    """The two money-relevant error rates (definitions are in the report)."""
    false_claims = [p for t, p in zip(true, pred, strict=True) if t == FALSE_CLAIM]
    deserving = [p for t, p in zip(true, pred, strict=True) if t in REFUND_CLASSES]
    refunded = sum(p in REFUND_CLASSES for p in false_claims)
    rejected = sum(p == FALSE_CLAIM for p in deserving)
    return {
        "wrong_refund_rate": refunded / len(false_claims) if false_claims else None,
        "wrong_refund_count": refunded,
        "false_claim_cases": len(false_claims),
        "wrong_rejection_rate": rejected / len(deserving) if deserving else None,
        "wrong_rejection_count": rejected,
        "refund_deserving_cases": len(deserving),
    }


def metrics(
    model: BaselineClassifier, rows: list[dict[str, Any]], cfg: dict[str, Any]
) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    probs = model.predict_proba_many([case_text(r, cfg) for r in rows])
    truth = np.array([CLASSES.index(r["label"]) for r in rows])
    pred = probs.argmax(axis=1)
    p, r, f1, support = precision_recall_fscore_support(
        truth, pred, labels=range(len(CLASSES)), zero_division=0
    )
    macro = precision_recall_fscore_support(
        truth, pred, labels=range(len(CLASSES)), average="macro", zero_division=0
    )
    return {
        "n": len(rows),
        "accuracy": float((truth == pred).mean()),
        "macro_f1": float(macro[2]),
        "per_class": {
            c: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f1[i]), "support": int(support[i])}
            for i, c in enumerate(CLASSES)
        },
        "confusion_matrix": {"labels": list(CLASSES), "rows_true_columns_predicted": confusion_matrix(truth, pred, labels=range(len(CLASSES))).tolist()},
        **rates([r["label"] for r in rows], [CLASSES[i] for i in pred]),
        "calibration_ece": expected_calibration_error(probs, truth),
        "log_loss": log_loss(probs, truth),
        "mean_confidence": float(probs.max(axis=1).mean()),
    }  # fmt: skip


def one_per_story(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for row in rows:
        key = row.get("story_key") or row["id"]
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


def split_report(
    model: BaselineClassifier, rows: list[dict[str, Any]], cfg: dict[str, Any]
) -> dict[str, Any]:
    sources = sorted({r["source"] for r in rows})
    return {
        **metrics(model, rows, cfg),
        "distinct_stories": len(one_per_story(rows)),
        "story_level": metrics(model, one_per_story(rows), cfg),
        "by_source": {
            s: metrics(model, [r for r in rows if r["source"] == s], cfg) for s in sources
        },
        "by_language_style": {
            s: metrics(model, [r for r in rows if r["language_style"] == s], cfg)
            for s in sorted({r["language_style"] for r in rows})
        },
    }


def to_case(row: dict[str, Any], text_override: dict[str, str] | None = None) -> DisputeCase:
    """A DisputeCase for the analyzer from a case record (timestamps are fixed assumptions)."""
    row = {**row, **(text_override or {})}
    events: list[tuple[str, datetime]] = []
    status = row["courier_status"]
    if status != "not_dispatched":
        events.append(("in_transit", T0 + 6 * HOUR))
        if status in ("delivered", "lost", "returned"):
            events.append((status, T0 + 30 * HOUR))
    delivered = status == "delivered"
    response = row["seller_response"].strip()
    return DisputeCase(
        dispute_id=row["id"], order_id="O-EVAL", amount_bdt=row["amount_bdt"], placed_at=T0,
        opened_at=T0 + 40 * HOUR, claim_text=row["buyer_claim"], courier_events=events,
        code_confirmed_at=T0 + 30.1 * HOUR if row["delivery_code_used"] and delivered else None,
        seller_response_text=response or None,
        seller_responded_at=T0 + 42 * HOUR if response else None,
        buyer_evidence=[row["buyer_evidence"]] if row["buyer_evidence"].strip() else [],
        seller_evidence=[row["seller_evidence"]] if row["seller_evidence"].strip() else [],
    )  # fmt: skip


def routing(
    model: BaselineClassifier, rows: list[dict[str, Any]], cfg: dict[str, Any]
) -> dict[str, Any]:
    """Run the full analyzer. The case records carry no history, so REPEAT_CLAIMANT never fires."""
    fast = fast_correct = fast_wrong_refund = 0
    reasons: dict[str, int] = {}
    recommended: dict[str, int] = {}
    for row in rows:
        result = analyze_case(to_case(row), model, cfg)
        recommended[result.recommendation] = recommended.get(result.recommendation, 0) + 1
        if result.route == Route.FAST_LANE_CONFIRM:
            fast += 1
            top = max(result.class_probs, key=result.class_probs.get)
            fast_correct += top == row["label"]
            fast_wrong_refund += row["label"] == FALSE_CLAIM and top in REFUND_CLASSES
        for reason in result.route_reasons:
            reasons[reason] = reasons.get(reason, 0) + 1
    n = len(rows)
    return {
        "n": n,
        "fast_lane_share": fast / n if n else None,
        "fast_lane_cases": fast,
        "fast_lane_accuracy": fast_correct / fast if fast else None,
        "fast_lane_wrong_refunds": fast_wrong_refund,
        "human_review_share": 1 - fast / n if n else None,
        "human_review_reasons": dict(sorted(reasons.items())),
        "recommendations": dict(sorted(recommended.items())),
    }


def injection_report(model: BaselineClassifier, cfg: dict[str, Any]) -> dict[str, Any]:
    rows = read("injection", cfg)
    if not rows:
        return {"n": 0}
    detected = changed_raw = changed_pipeline = human = detected_n = 0
    undetected_changed = undetected_n = 0
    for row in rows:
        field = (
            "seller_evidence"
            if row["injection_text"] in row["seller_evidence"]
            else "buyer_evidence"
        )
        twin = {field: row[field].replace(row["injection_text"], "").strip()}
        clean_pred = max(
            model.predict_proba(case_text({**row, **twin}, cfg)).items(), key=lambda i: i[1]
        )[0]
        raw_pred = max(model.predict_proba(case_text(row, cfg)).items(), key=lambda i: i[1])[0]
        changed_raw += raw_pred != clean_pred
        clean = analyze_case(to_case(row, twin), model, cfg)
        injected = analyze_case(to_case(row), model, cfg)
        screened = bool(scan(row["injection_text"]))
        detected_n += screened
        human += injected.route == Route.HUMAN_REVIEW
        different = injected.recommendation != clean.recommendation
        changed_pipeline += different
        if screened:
            detected += injected.injection_detected
        else:
            undetected_n += 1
            undetected_changed += different
    n = len(rows)
    return {
        "n": n,
        "screen_detected": detected_n,
        "screen_detection_rate": detected_n / n,
        "raw_text_prediction_changed_by_injection": changed_raw,
        "pipeline_recommendation_changed": changed_pipeline,
        "human_review_forced": human,
        "undetected_cases": undetected_n,
        "undetected_cases_with_changed_recommendation": undetected_changed,
        "note": (
            "Each injected case is compared with its twin (the same case without the added "
            "sentence). The twin is the baseline, so a change is caused by the sentence. Cases whose "
            "sentence the screen detects are always sent to a human; for those it misses, only "
            "the words in the sentence can move a bag-of-words model."
        ),
    }  # fmt: skip


def latency(
    model: BaselineClassifier, rows: list[dict[str, Any]], cfg: dict[str, Any]
) -> dict[str, Any]:
    texts = [case_text(r, cfg) for r in rows[:300]]
    model.predict_proba(texts[0])  # warm up
    times = []
    for text in texts:
        start = time.perf_counter()
        model.predict_proba(text)
        times.append((time.perf_counter() - start) * MS)
    budget = cfg["dispute"]["baseline"]["latency_budget_ms"]
    return {
        "samples": len(times), "mean_ms": float(np.mean(times)),
        "p95_ms": float(np.percentile(times, 95)), "max_ms": float(max(times)),
        "budget_ms": budget, "within_budget": bool(max(times) <= budget),
    }  # fmt: skip


def main() -> int:
    cfg = load_config()
    path = REPO_ROOT / cfg["paths"]["models_dir"] / "dispute_baseline_v1.joblib"
    if not path.exists():
        print("no dispute model: run `make train-dispute` first")
        return 1
    model = BaselineClassifier.load(path)
    splits = {name: read(name, cfg) for name in ("validation", "test1", "test2")}
    report: dict[str, Any] = {
        "model_version": model.version,
        "note": NOTE,
        "definitions": {
            "wrong_refund_rate": "share of true BUYER_FALSE_CLAIM cases predicted SELLER_FAULT or COURIER_ISSUE (a refund would be suggested)",
            "wrong_rejection_rate": "share of true SELLER_FAULT or COURIER_ISSUE cases predicted BUYER_FALSE_CLAIM (a rejection would be suggested)",
            "story_level": "the same metrics on one case per distinct combination of source texts",
            "validation": "the calibration was fitted on this split, so it is not an honest test",
        },
        "splits": {name: split_report(model, rows, cfg) for name, rows in splits.items() if rows},
        "routing": {name: routing(model, rows, cfg) for name, rows in splits.items() if rows and name != "validation"},
        "injection": injection_report(model, cfg),
        "latency": latency(model, splits["test1"] or splits["validation"], cfg),
        "trained_on": model.meta.get("trained_on"),
    }  # fmt: skip
    out = REPO_ROOT / cfg["paths"]["reports_dir"] / "dispute_eval_baseline.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    for name, info in report["splits"].items():
        print(
            f"{name:10s} n={info['n']:4d} stories={info['distinct_stories']:3d} macroF1={info['macro_f1']:.3f} acc={info['accuracy']:.3f} wrong-refund={info['wrong_refund_rate']} wrong-reject={info['wrong_rejection_rate']} ece={info['calibration_ece']:.3f}"
        )
    print(json.dumps(report["routing"], indent=1)[:600])
    print(json.dumps(report["injection"], indent=1)[:700])
    print(json.dumps(report["latency"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
