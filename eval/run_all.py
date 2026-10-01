"""Run every evaluation from the saved models and write reports/summary.json and the figures.

Usage: PYTHONPATH=backend:. python -m eval.run_all [--skip-trust]   (or `make eval`)

``summary.json`` copies numbers from the individual reports; it never recomputes or rounds them,
and every section that has no report says ``"status": "not_measured"`` with the reason. The
metrics page shows this file as it is.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from app.config import load_config
from app.trust.dataset import REPO_ROOT
from eval import figures, injection_eval, time_study, trust_eval

SCHEMA_VERSION = 1
NOT_MEASURED = "not_measured"
NOTE = (
    "Synthetic data only; not validated on real data. Simulated money. The numbers describe how "
    "the prototype behaves on the generated data and on developer-written test phrases."
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(directory: Path, name: str) -> dict[str, Any] | None:
    path = directory / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _missing(reason: str) -> dict[str, Any]:
    return {"status": NOT_MEASURED, "reason": reason}


def build_summary(reports: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    """Assemble the summary from the report dictionaries (``None`` = report does not exist)."""
    trust, injection = reports.get("trust_eval"), reports.get("injection_eval")
    dispute, study = reports.get("dispute_eval_baseline"), reports.get("time_study")

    if trust:
        trust_section: dict[str, Any] = {
            "status": "measured",
            "model_version": trust["model_version"],
            "target_false_positive_rate": trust["target_false_positive_rate"],
            "note": trust["note"],
            "test_v2": trust["test_v2"],
            "validation_v1_holdout": trust["validation_v1_holdout"],
            "reasons_v2": trust["reasons_v2"],
            "latency": trust["latency"],
        }
        fairness = {
            "status": "measured",
            "policies": trust["fairness_and_policy_v2"],
            "note": (
                "Three policies for sellers with little history, measured on the same test data. "
                "`override_default` is the configured one."
            ),
        }
    else:
        trust_section = _missing("reports/trust_eval.json is missing: run `make train` first")
        fairness = _missing("comes from the trust evaluation, which has not been run")

    if dispute:
        dispute_section: dict[str, Any] = {"status": "measured", "baseline": dispute}
    else:
        dispute_section = _missing(
            "no dispute classifier yet: the team's dispute cases (Step 5) are not in raw/"
        )

    if injection:
        injection_section: dict[str, Any] = {"status": "measured_on_developer_phrases", **injection}
    else:
        injection_section = _missing("reports/injection_eval.json is missing")

    return {
        "schema_version": SCHEMA_VERSION,
        "note": NOTE,
        "trust": trust_section,
        "fairness": fairness,
        "dispute_classifier": dispute_section,
        "routing": _missing(
            "routing coverage and wrong-refund / wrong-rejection rates need the dispute "
            "classifier and its test cases"
        ),
        "injection": injection_section,
        "time_study": {"status": "measured", **study} if study else _missing(
            "no timed analyst sessions yet: copy docs/time_study_template.json to "
            "data/time_study.json and fill it in"
        ),
    }  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--skip-trust", action="store_true", help="reuse reports/trust_eval.json as it is"
    )
    args = parser.parse_args()
    cfg = load_config()
    directory = REPO_ROOT / cfg["paths"]["reports_dir"]

    if not args.skip_trust:
        trust_eval.main()
    injection_eval.main()
    time_study.main()

    names = ("trust_eval", "injection_eval", "dispute_eval_baseline", "time_study")
    reports = {name: _load(directory, f"{name}.json") for name in names}
    summary = build_summary(reports)
    summary["sources"] = {
        f"{name}.json": _sha(directory / f"{name}.json") for name in names if reports[name]
    }
    path = directory / "summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    written = figures.make_all(summary, directory / "figures")
    print(f"wrote {path.relative_to(REPO_ROOT)}")
    for name in written:
        print(f"wrote {name.relative_to(REPO_ROOT)}")
    for key, section in summary.items():
        if isinstance(section, dict) and "status" in section:
            print(f"  {key}: {section['status']}")


if __name__ == "__main__":
    main()
