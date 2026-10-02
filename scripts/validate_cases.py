"""Validate the raw dispute case files and write the clean dataset (BLUEPRINT.md Section 8.3).

Usage (repository root): PYTHONPATH=backend:. python -m scripts.validate_cases

Reads raw/*.jsonl (one case per line), requires every field, checks the label, sub-type, language
style, courier status and types, drops cases that contain a phone-number-like string or repeat
an earlier case, tags each case with its batch (the file name), and writes
data/cases/dataset.jsonl and reports/dispute_cases_stats.json. Nothing is repaired silently: every
dropped case is counted by reason.
"""

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from app.config import load_config
from app.enums import CourierStatus, DisputeClass

REPO = Path(__file__).resolve().parents[1]
LABELS = {c.value for c in DisputeClass}
SUBTYPE_LABEL = {
    **dict.fromkeys(("SF1", "SF2", "SF3", "SF4"), "SELLER_FAULT"),
    **dict.fromkeys(("BF1", "BF2", "BF3", "BF4"), "BUYER_FALSE_CLAIM"),
    **dict.fromkeys(("CI1", "CI2", "CI3", "CI4"), "COURIER_ISSUE"),
    **dict.fromkeys(("IE1", "IE2", "IE3", "IE4"), "INSUFFICIENT_EVIDENCE"),
}
STYLES = {"standard", "banglish", "regional", "mixed"}
COURIER = {c.value for c in CourierStatus}
TEXT_FIELDS = ("buyer_claim", "seller_response", "buyer_evidence", "seller_evidence")
REQUIRED = (
    "id", "label", "subtype", "language_style", "product_category", "amount_bdt",
    "courier_status", "delivery_code_used", *TEXT_FIELDS, "has_injection", "source",
)  # fmt: skip
OPTIONAL = ("injection_text", "story_key")
BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
PHONE = re.compile(r"(?:\+?88)?01[3-9][\s-]?\d{2}[\s-]?\d{3}[\s-]?\d{3}")
LONG_NUMBER = re.compile(r"\d{10,}")
SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    return SPACES.sub(" ", unicodedata.normalize("NFKC", text).translate(BN_DIGITS)).strip().lower()


def has_phone_like(case: dict[str, Any]) -> bool:
    for field in TEXT_FIELDS:
        folded = unicodedata.normalize("NFKC", case[field]).translate(BN_DIGITS)
        compact = re.sub(r"[\s-]", "", folded)
        if PHONE.search(folded) or LONG_NUMBER.search(compact):
            return True
    return False


def problems(case: Any) -> list[str]:
    """Reasons the record is invalid (empty list = valid)."""
    if not isinstance(case, dict):
        return ["not_an_object"]
    found = [f"missing_{name}" for name in REQUIRED if name not in case]
    if found:
        return found
    out = []
    if case["label"] not in LABELS:
        out.append("bad_label")
    if case["subtype"] not in SUBTYPE_LABEL:
        out.append("bad_subtype")
    elif SUBTYPE_LABEL[case["subtype"]] != case["label"]:
        out.append("subtype_label_mismatch")
    if case["language_style"] not in STYLES:
        out.append("bad_language_style")
    if case["courier_status"] not in COURIER:
        out.append("bad_courier_status")
    if not isinstance(case["delivery_code_used"], bool) or not isinstance(
        case["has_injection"], bool
    ):
        out.append("bad_boolean")
    amount = case["amount_bdt"]
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        out.append("bad_amount")
    if not all(isinstance(case[f], str) for f in TEXT_FIELDS):
        out.append("bad_text_type")
    elif not case["buyer_claim"].strip():
        out.append("empty_buyer_claim")
    if not isinstance(case["id"], str) or not case["id"]:
        out.append("bad_id")
    if not isinstance(case["source"], str) or not case["source"]:
        out.append("bad_source")
    return out


def validate(raw_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    dropped: Counter[str] = Counter()
    seen_text: set[str] = set()
    seen_id: set[str] = set()
    files = sorted(raw_dir.glob("*.jsonl"))
    read = 0
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            read += 1
            try:
                case = json.loads(line)
            except json.JSONDecodeError:
                dropped["invalid_json"] += 1
                continue
            bad = problems(case)
            if bad:
                dropped.update(bad[:1])
                continue
            if has_phone_like(case):
                dropped["phone_like_number"] += 1
                continue
            if case["id"] in seen_id:
                dropped["duplicate_id"] += 1
                continue
            key = "|".join(normalize(case[f]) for f in TEXT_FIELDS) + f"|{case['label']}"
            if key in seen_text:
                dropped["duplicate_text"] += 1
                continue
            seen_id.add(case["id"])
            seen_text.add(key)
            kept.append({**case, "batch": path.stem})
    stats = {
        "files": len(files),
        "read": read,
        "kept": len(kept),
        "dropped": dict(sorted(dropped.items())),
        "by_label": dict(sorted(Counter(c["label"] for c in kept).items())),
        "by_subtype": dict(sorted(Counter(c["subtype"] for c in kept).items())),
        "by_source": dict(sorted(Counter(c["source"] for c in kept).items())),
        "by_language_style": dict(sorted(Counter(c["language_style"] for c in kept).items())),
        "injection_cases": sum(c["has_injection"] for c in kept),
        "manual_review": {
            "done": False,
            "note": "Nobody has read a sample of the cases and removed wrong-label or unrealistic "
            "ones. The blueprint asks the team to read about 10% and record the share deleted.",
        },
    }
    return kept, stats


def main() -> int:
    cfg = load_config()["dispute"]["cases"]
    raw_dir, out_dir = REPO / cfg["raw_dir"], REPO / cfg["out_dir"]
    if not any(raw_dir.glob("*.jsonl")):
        print(f"no case files in {raw_dir}: add raw/<source>_<SUBTYPE>.jsonl files")
        return 1
    kept, stats = validate(raw_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(c, ensure_ascii=False) for c in kept) + "\n"
    (out_dir / "dataset.jsonl").write_text(text, encoding="utf-8")
    report = REPO / load_config()["paths"]["reports_dir"] / "dispute_cases_stats.json"
    report.write_text(json.dumps(stats, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"read {stats['read']} cases from {stats['files']} files, kept {stats['kept']}")
    for name in ("dropped", "by_label", "by_source", "by_language_style"):
        print(f"  {name}: {json.dumps(stats[name], ensure_ascii=False)}")
    print(f"  by_subtype: {json.dumps(stats['by_subtype'])}")
    print(f"wrote {out_dir / 'dataset.jsonl'} and {report.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
