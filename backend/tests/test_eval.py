"""The evaluation summary: every number comes from a report, and missing ones say so."""

import json
from pathlib import Path

import pytest

from app.config import load_config
from eval import injection_eval, time_study
from eval.injection_samples import HARMLESS, INJECTIONS
from eval.run_all import build_summary

REPO = Path(__file__).resolve().parents[2]


def real_reports() -> dict:
    out = {}
    for name in ("trust_eval", "injection_eval", "dispute_eval_baseline", "time_study"):
        path = REPO / "reports" / f"{name}.json"
        out[name] = json.loads(path.read_text()) if path.exists() else None
    return out


def test_without_any_report_every_section_is_not_measured() -> None:
    summary = build_summary({})
    for key in ("trust", "fairness", "dispute_classifier", "routing", "injection", "time_study"):
        assert summary[key]["status"] == "not_measured", key
        assert summary[key]["reason"]
    assert "not validated on real data" in summary["note"]


def test_numbers_are_copied_not_recomputed() -> None:
    reports = real_reports()
    if reports["trust_eval"] is None:
        pytest.skip("run `make train` and `make eval` first")
    summary = build_summary(reports)
    trust = reports["trust_eval"]
    assert summary["trust"]["test_v2"] == trust["test_v2"]
    assert summary["fairness"]["policies"] == trust["fairness_and_policy_v2"]
    assert summary["trust"]["latency"] == trust["latency"]


def test_dispute_and_routing_are_not_measured_without_the_dispute_report() -> None:
    summary = build_summary({**real_reports(), "dispute_eval_baseline": None})
    assert summary["dispute_classifier"]["status"] == "not_measured"
    assert summary["routing"]["status"] == "not_measured"


def test_dispute_numbers_are_copied_from_the_report() -> None:
    reports = real_reports()
    if reports["dispute_eval_baseline"] is None:
        pytest.skip("run `make cases train-dispute eval` first")
    summary = build_summary(reports)
    assert summary["dispute_classifier"]["baseline"] == reports["dispute_eval_baseline"]
    assert summary["routing"]["test1"] == reports["dispute_eval_baseline"]["routing"]["test1"]


def test_injection_screen_regression_phrases() -> None:
    cfg = load_config()
    result = injection_eval.invariance(cfg)
    assert result["pairs_checked"] == 4 * 2 * len(INJECTIONS)
    for key in (
        "classifier_text_changed", "probabilities_changed", "recommendation_changed",
        "flags_changed_beyond_injection_flag", "human_review_not_forced",
    ):  # fmt: skip
        assert result[key] == 0, key
    assert HARMLESS  # the false-alarm side is covered in test_analyzer


GOOD = {"cases": [
    {"case_id": "C1", "seconds_without_tool": 600, "seconds_with_tool": 240},
    {"case_id": "C2", "seconds_without_tool": 300, "seconds_with_tool": 330},
    {"case_id": "C3", "seconds_without_tool": 420, "seconds_with_tool": 180},
]}  # fmt: skip


def test_time_study_aggregates_what_was_measured() -> None:
    out = time_study.aggregate(GOOD)
    assert out["n_cases"] == 3
    assert out["median_seconds_without_tool"] == 420
    assert out["median_seconds_with_tool"] == 240
    assert out["cases_faster_with_tool"] == 2
    assert out["median_time_saved_share"] == pytest.approx((420 - 240) / 420)


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"cases": []},
        {"cases": [{"case_id": "EXAMPLE-1", "seconds_without_tool": 0, "seconds_with_tool": 0}]},
        {"cases": [{"case_id": "C", "seconds_without_tool": -5, "seconds_with_tool": 10}]},
        {"cases": [{"case_id": "C", "seconds_without_tool": "10", "seconds_with_tool": 10}]},
    ],
)
def test_time_study_refuses_empty_template_or_invalid_numbers(bad: dict) -> None:
    with pytest.raises(time_study.TimeStudyError):
        time_study.aggregate(bad)
