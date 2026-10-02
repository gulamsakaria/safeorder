"""Write the dispute case files in raw/ (BLUEPRINT.md Section 8.3), from the assistant-written bank.

Usage (repository root): PYTHONPATH=backend:. python -m scripts.make_cases

**Provenance, stated plainly:** every text in ``scripts/case_bank`` was written by the Claude
assistant in this repository, not by ChatGPT, not by Gemini, not by the team. This script only
combines those texts with seeded random choices (product, amount, courier status, small
adornments). So the three "sources" below share one author: the cross-source test the blueprint
describes (ChatGPT trains, Gemini tests, the team's own cases are the cleanest test) is NOT
reproduced. What the split does guarantee is that no claim text and no combination of texts used
for a test appears in training. When the team's own cases are added to raw/ (source ``team``), they
join Test 2 and are reported separately.

Sources and their role: claude_a trains (and a ``_val`` part validates), claude_b is Test 1,
claude_c is Test 2, claude_inj is the injection set (never trained on).
"""

import json
import random
from pathlib import Path
from typing import Any

from scripts.case_bank import (
    buyer_false_claim,
    courier_issue,
    injection,
    insufficient,
    seller_fault,
)
from scripts.case_bank.claims import FAMILIES

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "raw"

LABELS = {
    "SELLER_FAULT": seller_fault.SUBTYPES,
    "BUYER_FALSE_CLAIM": buyer_false_claim.SUBTYPES,
    "COURIER_ISSUE": courier_issue.SUBTYPES,
    "INSUFFICIENT_EVIDENCE": insufficient.SUBTYPES,
}
SUBTYPES = {st: (label, spec) for label, group in LABELS.items() for st, spec in group.items()}

# Which positions of each text list belong to which part (train / val / test1 / test2).
SPLIT_SIZES = {16: (2, 3, 2), 10: (1, 2, 2), 8: (1, 2, 1)}  # (val, test1, test2) held-out counts
PARTS = ("train", "val", "test1", "test2")

PRODUCTS = {
    "clothing": [("শাড়ি", "saree"), ("পাঞ্জাবি", "panjabi"), ("থ্রি-পিস", "three-piece")],
    "cosmetics": [
        ("ফেসওয়াশ", "facewash"),
        ("লিপস্টিক", "lipstick"),
        ("স্কিন কেয়ার সেট", "skincare set"),
    ],
    "electronics": [("ইয়ারফোন", "earphone"), ("পাওয়ার ব্যাংক", "power bank"), ("স্মার্টওয়াচ", "smartwatch")],
    "household": [("রাইস কুকার", "rice cooker"), ("ব্লেন্ডার", "blender"), ("বিছানার চাদর", "bedsheet")],
    "food": [("মধু", "modhu"), ("খেজুর", "khejur"), ("আচার", "achar")],
    "shoes": [("স্যান্ডেল", "sandal"), ("স্নিকার্স", "sneakers"), ("চামড়ার জুতা", "leather shoe")],
    "books": [("বইয়ের সেট", "boi er set"), ("গল্পের বই", "golper boi")],
    "accessories": [("হাতঘড়ি", "watch"), ("ব্যাগ", "bag"), ("চশমা", "sunglasses")],
}
AMOUNT_RANGE = {
    "clothing": (600, 3500), "cosmetics": (400, 2500), "electronics": (800, 9000),
    "household": (700, 6000), "food": (300, 1800), "shoes": (900, 3800),
    "books": (250, 1800), "accessories": (400, 4000),
}  # fmt: skip
PREFIX = {
    "standard": ["", "", "", "নমস্কার, ", "ভাই, ", "আপু, "],
    "banglish": ["", "", "", "vai, ", "apu, ", "bhaiya, "],
    "regional": ["", "", "", "ভাই, ", "আপা, "],
    "mixed": ["", "", "", "Sir, ", "ভাই, ", "Hi, "],
}
SUFFIX = {
    "standard": ["", "", "", " দ্রুত সমাধান চাই।", " দয়া করে দেখুন।"],
    "banglish": ["", "", "", " taratari dekhen.", " help korun."],
    "regional": ["", "", "", " তাড়াতাড়ি দেখেন।"],
    "mixed": ["", "", "", " please look into it.", " জলদি দেখুন।"],
}
DROPOUT = 0.10  # chance that a seller response or evidence text is simply missing


def held_out(n: int) -> dict[str, list[int]]:
    """Positions of a text list that each part may use. The first ones are training."""
    val, t1, t2 = SPLIT_SIZES[n]
    train = n - val - t1 - t2
    cuts = {"train": range(0, train), "val": range(train, train + val)}
    cuts["test1"] = range(train + val, train + val + t1)
    cuts["test2"] = range(train + val + t1, n)
    return {part: list(positions) for part, positions in cuts.items()}


def weighted(rng: random.Random, weights: dict[str, float]) -> str:
    keys = list(weights)
    return rng.choices(keys, [weights[k] for k in keys])[0]


def make_case(
    rng: random.Random, part: str, subtype: str, source: str, number: int
) -> dict[str, Any]:
    label, spec = SUBTYPES[subtype]
    claims = FAMILIES[spec["claim_family"]]
    claim_i = rng.choice(held_out(len(claims))[part])
    resp_i = rng.choice(held_out(len(spec["response"]))[part])
    bev_i = rng.choice(held_out(len(spec["buyer_ev"]))[part])
    sev_i = rng.choice(held_out(len(spec["seller_ev"]))[part])
    style, claim = claims[claim_i]

    category = rng.choice(sorted(PRODUCTS))
    product_bn, product_roman = rng.choice(PRODUCTS[category])
    amount = round(rng.uniform(*AMOUNT_RANGE[category]) / 10) * 10
    slots = {
        "p": product_bn if style in ("standard", "regional") else product_roman,
        "amt": amount,
        "d": rng.randint(4, 14),
    }
    claim = PREFIX[style][rng.randrange(len(PREFIX[style]))] + claim.format(**slots)
    claim += SUFFIX[style][rng.randrange(len(SUFFIX[style]))]

    response, buyer_ev, seller_ev = (
        spec["response"][resp_i],
        spec["buyer_ev"][bev_i],
        spec["seller_ev"][sev_i],
    )
    if rng.random() < DROPOUT:
        response, seller_ev = "", ""
    if rng.random() < DROPOUT:
        buyer_ev = ""
    code = rng.random() < spec["code_used"]
    return {
        "id": f"{source}-{subtype}-{number:03d}", "label": label, "subtype": subtype,
        "language_style": style, "product_category": category, "amount_bdt": int(amount),
        "courier_status": weighted(rng, spec["courier"]), "delivery_code_used": code,
        "buyer_claim": claim, "seller_response": response,
        "buyer_evidence": buyer_ev, "seller_evidence": seller_ev,
        "has_injection": False, "source": source,
        "story_key": f"{spec['claim_family']}:{claim_i}|r{resp_i}|b{bev_i}|s{sev_i}",
    }  # fmt: skip


def write(name: str, rows: list[dict[str, Any]]) -> None:
    RAW.mkdir(exist_ok=True)
    text = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
    (RAW / f"{name}.jsonl").write_text(text, encoding="utf-8")


def injection_cases(rng: random.Random) -> dict[str, list[dict[str, Any]]]:
    """Six per label: a test-style case with an instruction sentence added to the evidence."""
    out: dict[str, list[dict[str, Any]]] = {}
    for label, group in LABELS.items():
        rows = []
        for number in range(1, 7):
            subtype = sorted(group)[(number - 1) % len(group)]
            case = make_case(rng, "test2", subtype, "claude_inj", number)
            seller_side = label == "COURIER_ISSUE" and number % 2 == 0
            sentence = rng.choice(injection.SELLER_SIDE if seller_side else injection.BUYER_SIDE)
            field = "seller_evidence" if seller_side else "buyer_evidence"
            case[field] = f"{case[field]} {sentence}".strip()
            case["injection_text"] = sentence
            case["has_injection"] = True
            case["id"] = f"claude_inj-{label}-{number:03d}"
            rows.append(case)
        out[label] = rows
    return out


PLAN = (  # (source, part, per sub-type, batch suffix)
    ("claude_a", "train", 24, ""),
    ("claude_a", "val", 6, "_val"),
    ("claude_b", "test1", 20, ""),
    ("claude_c", "test2", 20, ""),
)


PROVENANCE = """# Provenance of the case files in this folder

| Item | Value |
|---|---|
| Author of every `claude_*` file | the Claude AI assistant (Anthropic), working in this repository, on {date} |
| Method | texts written by the assistant in `scripts/case_bank/`; combined with seeded random choices (product, amount, courier status, small adornments) by `scripts/make_cases.py` (seed {seed}) |
| NOT used | ChatGPT, Gemini, any other tool; real people's messages, names, phone numbers, brands |
| Prompt | none: the assistant wrote the texts directly; there is no master prompt to record |
| Human review | **none**: nobody has read a sample or deleted a case |
| Language review | the Bangla (especially the "regional" style) needs a native speaker |

Why this matters: the blueprint's design (ChatGPT trains, Gemini tests, team-written cases are the
cleanest test) is not reproduced. All splits here share one author, so evaluation numbers are
optimistic for other authors and for real disputes (see `docs/dataset_card_dispute_cases.md`).

## Files and roles

| Source (`source` field) | Role | Files |
|---|---|---|
| `claude_a` | train (`..._val` files: validation) | `claude_a_<SUBTYPE>.jsonl`, `claude_a_<SUBTYPE>_val.jsonl` |
| `claude_b` | Test 1 | `claude_b_<SUBTYPE>.jsonl` |
| `claude_c` | Test 2 | `claude_c_<SUBTYPE>.jsonl` |
| `claude_inj` | injection set (never trained on) | `injection_claude_inj_<LABEL>.jsonl` |

## Adding the team's own cases

Put `team_<SUBTYPE>.jsonl` (and, for ChatGPT or Gemini batches, `chatgpt_<SUBTYPE>.jsonl`,
`gemini_<SUBTYPE>.jsonl`) here, one JSON object per line with the fields of BLUEPRINT.md Section 8.3,
and the right `source` value. Record tool, version, date and prompt version for each batch in the
table above (this file is regenerated by `make make-cases`, so keep your own notes in
`raw/PROVENANCE_team.md`). Then run `make cases train-dispute eval docs`. The reports show each source
separately.
"""


def write_provenance() -> None:
    (RAW / "PROVENANCE.md").write_text(
        PROVENANCE.format(date="2026-10-02", seed=SEED), encoding="utf-8"
    )


SEED = 20261001


def main() -> None:
    rng = random.Random(SEED)
    total = 0
    for source, part, count, suffix in PLAN:
        for subtype in SUBTYPES:
            rows = [
                make_case(rng, part, subtype, f"{source}{suffix}", n) for n in range(1, count + 1)
            ]
            for row in rows:
                row["source"] = source
            write(f"{source}_{subtype}{suffix}", rows)
            total += len(rows)
    for label, rows in injection_cases(rng).items():
        write(f"injection_claude_inj_{label}", rows)
        total += len(rows)
    write_provenance()
    print(f"wrote {total} cases into raw/")


if __name__ == "__main__":
    main()
