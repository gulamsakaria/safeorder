"""Analyst time study (BLUEPRINT.md Section 10).

Usage: PYTHONPATH=backend:. python -m eval.time_study
Input: data/time_study.json (copy docs/time_study_template.json and fill it in with real timings).
Output: reports/time_study.json. Without the input file nothing is written and the metrics page
shows "not measured". The script only aggregates what people measured; it invents nothing.
"""

import json
import statistics
from pathlib import Path
from typing import Any

from app.config import load_config
from app.trust.dataset import REPO_ROOT

INPUT = Path("data") / "time_study.json"
PLACEHOLDER_IDS = ("EXAMPLE",)


class TimeStudyError(ValueError):
    pass


def aggregate(raw: dict[str, Any]) -> dict[str, Any]:
    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise TimeStudyError("the study needs a non-empty list of cases")
    without, with_tool = [], []
    for case in cases:
        cid = str(case.get("case_id", ""))
        if cid.startswith(PLACEHOLDER_IDS):
            raise TimeStudyError(f"{cid}: replace the template example with real timings")
        a, b = case.get("seconds_without_tool"), case.get("seconds_with_tool")
        for value in (a, b):
            if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
                raise TimeStudyError(f"{cid}: timings must be positive numbers of seconds")
        without.append(float(a))
        with_tool.append(float(b))
    median_without, median_with = statistics.median(without), statistics.median(with_tool)
    return {
        "n_cases": len(cases),
        "analyst_label": raw.get("study", {}).get("analyst_label"),
        "median_seconds_without_tool": median_without,
        "median_seconds_with_tool": median_with,
        "median_time_saved_share": (median_without - median_with) / median_without,
        "cases_faster_with_tool": sum(b < a for a, b in zip(without, with_tool, strict=True)),
        "note": (
            "Small, unblinded timing study by the team; the same people knew both conditions. "
            "An indication, not evidence of a general effect."
        ),
    }


def main() -> None:
    cfg = load_config()
    source = REPO_ROOT / INPUT
    target = REPO_ROOT / cfg["paths"]["reports_dir"] / "time_study.json"
    if not source.exists():
        target.unlink(missing_ok=True)
        print(f"{INPUT} not found: time study not measured")
        return
    report = aggregate(json.loads(source.read_text(encoding="utf-8")))
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"wrote {target.relative_to(REPO_ROOT)} ({report['n_cases']} cases)")


if __name__ == "__main__":
    main()
