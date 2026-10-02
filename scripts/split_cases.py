"""Split the clean dataset into train / validation / test1 / test2 / injection (Section 8.3).

Usage (repository root): PYTHONPATH=backend:. python -m scripts.split_cases

* The split is by **source and batch**, never by random row: the sources of each role come from
  ``dispute.cases.roles`` in config/config.yaml; batches named ``..._val`` are the validation split.
* A source that no role lists stops the script (nothing is guessed).
* Cases with ``has_injection`` go only to the injection set; it is never trained on.
* A claim text that appears in more than one of train, validation, test1, test2 is removed from the
  later split (train wins, then validation, test1, test2) and counted. The injection set must not
  share claim text with train, validation or test1; it may share it with test2 by design (its
  cases are test-style cases with an instruction sentence added).
* The script then asserts: no batch in two splits, no shared claim text, no shared story key.
"""

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from app.config import load_config
from scripts.validate_cases import normalize

REPO = Path(__file__).resolve().parents[1]
ORDER = ("train", "validation", "test1", "test2")
FILES = {**{s: f"{s}.jsonl" for s in ORDER}, "injection": "injection.jsonl"}


class SplitError(RuntimeError):
    pass


def assign(
    cases: list[dict[str, Any]], roles: dict[str, list[str]], val_suffix: str
) -> dict[str, list]:
    role_of = {source: role for role, sources in roles.items() for source in sources}
    splits: dict[str, list[dict[str, Any]]] = {name: [] for name in FILES}
    unknown = sorted({c["source"] for c in cases} - set(role_of))
    if unknown:
        raise SplitError(f"sources not listed in dispute.cases.roles: {', '.join(unknown)}")
    for case in cases:
        role = role_of[case["source"]]
        if case["has_injection"]:
            target = "injection"
        elif role == "injection":
            raise SplitError(
                f"{case['id']}: a case from an injection source has has_injection=false"
            )
        elif role == "train" and case["batch"].endswith(val_suffix):
            target = "validation"
        else:
            target = role
        splits[target].append(case)
    return splits


def remove_shared_claims(splits: dict[str, list]) -> dict[str, int]:
    """Drop later-split cases whose claim text already appears in an earlier split."""
    seen: dict[str, str] = {}
    removed: Counter[str] = Counter()
    for name in ORDER:
        kept = []
        for case in splits[name]:
            claim = normalize(case["buyer_claim"])
            if claim in seen and seen[claim] != name:
                removed[name] += 1
                continue
            seen[claim] = name
            kept.append(case)
        splits[name] = kept
    guarded = {
        c
        for n in ("train", "validation", "test1")
        for c in map(lambda x: normalize(x["buyer_claim"]), splits[n])
    }
    kept = []
    for case in splits["injection"]:
        if normalize(case["buyer_claim"]) in guarded:
            removed["injection"] += 1
        else:
            kept.append(case)
    splits["injection"] = kept
    return dict(removed)


def check(splits: dict[str, list]) -> None:
    """The guarantees the report relies on. Raises SplitError when one fails."""
    batches: dict[str, str] = {}
    for name, cases in splits.items():
        for batch in {c["batch"] for c in cases}:
            if batch in batches and batches[batch] != name:
                raise SplitError(f"batch {batch} is in both {batches[batch]} and {name}")
            batches[batch] = name
    claims: dict[str, str] = {}
    for name in ORDER:
        for case in splits[name]:
            claim = normalize(case["buyer_claim"])
            if claims.setdefault(claim, name) != name:
                raise SplitError(f"claim text shared by {claims[claim]} and {name}: {claim[:60]}")
    stories: dict[str, str] = {}
    for name in ORDER:
        for case in splits[name]:
            key = case.get("story_key")
            if key and stories.setdefault(key, name) != name:
                raise SplitError(f"story {key} is in both {stories[key]} and {name}")
    train_side = {normalize(c["buyer_claim"]) for n in ("train", "validation") for c in splits[n]}
    for case in splits["injection"]:
        if normalize(case["buyer_claim"]) in train_side:
            raise SplitError(f"injection case {case['id']} shares claim text with training")
    if any(not c["has_injection"] for c in splits["injection"]):
        raise SplitError("the injection set holds a case without an injection")
    if any(c["has_injection"] for n in ORDER for c in splits[n]):
        raise SplitError("an injection case is in a training or test split")


def summarize(splits: dict[str, list], removed: dict[str, int]) -> dict[str, Any]:
    def count(name: str, field: str) -> dict[str, int]:
        return dict(sorted(Counter(c[field] for c in splits[name]).items()))

    return {
        "removed_for_shared_claim_text": removed,
        "splits": {
            name: {
                "n": len(cases),
                "batches": len({c["batch"] for c in cases}),
                "distinct_stories": len({c.get("story_key") for c in cases if c.get("story_key")}),
                "by_label": count(name, "label"),
                "by_subtype": count(name, "subtype"),
                "by_source": count(name, "source"),
                "by_language_style": count(name, "language_style"),
            }
            for name, cases in splits.items()
        },
        "guarantees_checked": [
            "no batch in two splits",
            "no claim text shared by train, validation, test1 and test2",
            "no story key shared by train, validation, test1 and test2",
            "injection set disjoint from train and validation in claim text",
            "injection cases only in the injection set",
        ],
    }


def main() -> int:
    cfg = load_config()
    case_cfg = cfg["dispute"]["cases"]
    out_dir = REPO / case_cfg["out_dir"]
    dataset = out_dir / "dataset.jsonl"
    if not dataset.exists():
        print(f"{dataset} not found: run scripts.validate_cases first")
        return 1
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
    try:
        splits = assign(cases, case_cfg["roles"], case_cfg["validation_batch_suffix"])
        removed = remove_shared_claims(splits)
        check(splits)
    except SplitError as error:
        print(f"FAILED: {error}")
        return 1
    for name, filename in FILES.items():
        text = "\n".join(json.dumps(c, ensure_ascii=False) for c in splits[name])
        (out_dir / filename).write_text(text + ("\n" if text else ""), encoding="utf-8")
    report = summarize(splits, removed)
    path = REPO / cfg["paths"]["reports_dir"] / "dispute_cases_splits.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    for name, info in report["splits"].items():
        counts = (
            f"n={info['n']:4d} batches={info['batches']:3d} stories={info['distinct_stories']:4d}"
        )
        print(f"{name:10s} {counts} sources={info['by_source']}")
    print(f"removed for shared claim text: {removed or 'none'}")
    print(f"wrote {path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
