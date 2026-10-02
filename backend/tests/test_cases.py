"""Dispute case files: validation, leak-free splits, and the case bank's own design (Steps 5)."""

import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.config import load_config
from scripts import make_cases, split_cases, validate_cases
from scripts.case_bank.claims import FAMILIES
from scripts.validate_cases import normalize

REPO = Path(__file__).resolve().parents[2]
CFG = load_config()["dispute"]["cases"]


def good(**overrides) -> dict:
    base = {
        "id": "x-SF1-001", "label": "SELLER_FAULT", "subtype": "SF1", "language_style": "standard",
        "product_category": "shoes", "amount_bdt": 1200, "courier_status": "not_dispatched",
        "delivery_code_used": False, "buyer_claim": "পণ্য পাইনি।", "seller_response": "",
        "buyer_evidence": "মেসেজ দিয়েছি।", "seller_evidence": "", "has_injection": False,
        "source": "ai_a",
    }  # fmt: skip
    base.update(overrides)
    return base


# ---- validation ----------------------------------------------------------------------------------


def test_a_good_record_has_no_problems() -> None:
    assert validate_cases.problems(good()) == []


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"label": "NOPE"}, "bad_label"),
        ({"subtype": "ZZ9"}, "bad_subtype"),
        ({"subtype": "BF1"}, "subtype_label_mismatch"),
        ({"language_style": "klingon"}, "bad_language_style"),
        ({"courier_status": "teleported"}, "bad_courier_status"),
        ({"amount_bdt": 0}, "bad_amount"),
        ({"amount_bdt": "100"}, "bad_amount"),
        ({"amount_bdt": True}, "bad_amount"),
        ({"delivery_code_used": "yes"}, "bad_boolean"),
        ({"buyer_claim": "   "}, "empty_buyer_claim"),
        ({"buyer_evidence": 5}, "bad_text_type"),
        ({"id": ""}, "bad_id"),
    ],
)
def test_invalid_records_are_named(change: dict, expected: str) -> None:
    assert validate_cases.problems(good(**change))[0] == expected


def test_missing_fields_are_reported_and_non_objects_rejected() -> None:
    record = good()
    del record["seller_evidence"]
    assert validate_cases.problems(record) == ["missing_seller_evidence"]
    assert validate_cases.problems([1, 2]) == ["not_an_object"]


@pytest.mark.parametrize(
    "text",
    [
        "call me on 01712345678",
        "০১৭১২৩৪৫৬৭৮ এ ফোন করুন",
        "+8801712-345-678",
        "01712 345 678",
        "nid 1234567890123",
    ],
)
def test_phone_like_strings_are_detected(text: str) -> None:
    assert validate_cases.has_phone_like(good(buyer_evidence=text))


@pytest.mark.parametrize(
    "text", ["আমার {amt} টাকা 6440 গেছে", "৫০০০ টাকা", "order 12345", "৭ দিন হয়েছে"]
)
def test_ordinary_numbers_are_not_phone_numbers(text: str) -> None:
    assert not validate_cases.has_phone_like(good(buyer_evidence=text))


def test_validate_drops_bad_phone_and_duplicate_cases(tmp_path) -> None:
    rows = [
        good(),
        good(id="x-SF1-002"),  # same texts: duplicate
        good(id="x-SF1-003", buyer_evidence="ফোন 01712345678"),
        good(id="x-SF1-004", label="NOPE"),
        good(id="x-SF1-005", buyer_claim="একদম আলাদা অভিযোগ"),
    ]
    (tmp_path / "a_SF1.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\nnot json\n"
    )
    kept, stats = validate_cases.validate(tmp_path)
    assert [c["id"] for c in kept] == ["x-SF1-001", "x-SF1-005"]
    assert kept[0]["batch"] == "a_SF1"
    assert stats["dropped"] == {
        "bad_label": 1,
        "duplicate_text": 1,
        "invalid_json": 1,
        "phone_like_number": 1,
    }
    assert stats["manual_review"]["done"] is False


# ---- splitting -----------------------------------------------------------------------------------


def case(i: str, source: str, batch: str, claim: str, **extra) -> dict:
    return {**good(id=i, source=source, buyer_claim=claim), "batch": batch, **extra}


ROLES = {"train": ["a"], "test1": ["b"], "test2": ["c"], "injection": ["inj"]}


def test_assign_uses_sources_batches_and_the_injection_flag() -> None:
    cases = [
        case("1", "a", "a_SF1", "c1"),
        case("2", "a", "a_SF1_val", "c2"),
        case("3", "b", "b_SF1", "c3"),
        case("4", "c", "c_SF1", "c4"),
        case("5", "inj", "inj_X", "c5", has_injection=True),
    ]
    splits = split_cases.assign(cases, ROLES, "_val")
    assert {k: [c["id"] for c in v] for k, v in splits.items()} == {
        "train": ["1"], "validation": ["2"], "test1": ["3"], "test2": ["4"], "injection": ["5"],
    }  # fmt: skip


def test_an_unlisted_source_stops_the_split() -> None:
    with pytest.raises(split_cases.SplitError, match="not listed"):
        split_cases.assign([case("1", "mystery", "m_SF1", "c")], ROLES, "_val")


def test_an_injection_source_without_an_injection_is_refused() -> None:
    with pytest.raises(split_cases.SplitError):
        split_cases.assign([case("1", "inj", "inj_X", "c")], ROLES, "_val")


def test_shared_claim_text_is_removed_from_the_later_split_and_counted() -> None:
    splits = {
        "train": [case("1", "a", "a_1", "Same claim")],
        "validation": [],
        "test1": [case("2", "b", "b_1", "  same   CLAIM "), case("3", "b", "b_1", "other")],
        "test2": [],
        "injection": [case("4", "inj", "i_1", "same claim", has_injection=True)],
    }
    removed = split_cases.remove_shared_claims(splits)
    assert removed == {"test1": 1, "injection": 1}
    assert [c["id"] for c in splits["test1"]] == ["3"]
    split_cases.check(splits)


def test_check_catches_a_batch_in_two_splits_and_shared_claims_and_stories() -> None:
    base = {"train": [], "validation": [], "test1": [], "test2": [], "injection": []}
    with pytest.raises(split_cases.SplitError, match="batch"):
        split_cases.check(
            {**base, "train": [case("1", "a", "B", "x")], "test1": [case("2", "b", "B", "y")]}
        )
    with pytest.raises(split_cases.SplitError, match="claim"):
        split_cases.check(
            {**base, "train": [case("1", "a", "A", "x")], "test1": [case("2", "b", "B", "x")]}
        )
    with pytest.raises(split_cases.SplitError, match="story"):
        split_cases.check({
            **base,
            "train": [case("1", "a", "A", "x", story_key="k")],
            "test1": [case("2", "b", "B", "y", story_key="k")],
        })  # fmt: skip
    with pytest.raises(split_cases.SplitError, match="injection"):
        split_cases.check({**base, "injection": [case("1", "inj", "I", "z", has_injection=False)]})
    with pytest.raises(split_cases.SplitError, match="injection"):
        split_cases.check({**base, "train": [case("1", "a", "A", "x", has_injection=True)]})


# ---- the committed case files --------------------------------------------------------------------


def load(name: str) -> list[dict]:
    path = REPO / CFG["out_dir"] / f"{name}.jsonl"
    if not path.exists():
        pytest.skip("run `make cases` first")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


SPLITS = ("train", "validation", "test1", "test2", "injection")


def test_the_real_splits_pass_every_guarantee() -> None:
    splits = {name: load(name) for name in SPLITS}
    split_cases.check(splits)
    assert split_cases.remove_shared_claims({k: list(v) for k, v in splits.items()}) == {}


@pytest.mark.parametrize("name", ["train", "validation", "test1", "test2"])
def test_every_label_and_subtype_is_present_in_each_split(name: str) -> None:
    rows = load(name)
    assert {r["label"] for r in rows} == set(validate_cases.LABELS)
    assert {r["subtype"] for r in rows} == set(validate_cases.SUBTYPE_LABEL)


def test_the_injection_set_is_separate_and_covers_every_label() -> None:
    rows = load("injection")
    assert rows and all(
        r["has_injection"] and r["injection_text"] in (r["buyer_evidence"] + r["seller_evidence"])
        for r in rows
    )
    assert {r["label"] for r in rows} == set(validate_cases.LABELS)
    for name in ("train", "validation", "test1", "test2"):
        assert not any(r["has_injection"] for r in load(name))


def test_dataset_file_has_no_phone_numbers_and_no_duplicate_ids() -> None:
    rows = [
        json.loads(x) for x in (REPO / CFG["out_dir"] / "dataset.jsonl").read_text().splitlines()
    ]
    assert not any(validate_cases.has_phone_like(r) for r in rows)
    assert len({r["id"] for r in rows}) == len(rows)


def test_stats_report_states_that_nobody_reviewed_the_cases() -> None:
    stats = json.loads((REPO / "reports" / "dispute_cases_stats.json").read_text())
    assert stats["manual_review"]["done"] is False
    dataset = (REPO / CFG["out_dir"] / "dataset.jsonl").read_text().splitlines()
    assert stats["kept"] == len(dataset)


# ---- the case bank's design ----------------------------------------------------------------------


def test_held_out_positions_partition_a_list_without_overlap() -> None:
    for n in make_cases.SPLIT_SIZES:
        parts = make_cases.held_out(n)
        flat = [i for part in make_cases.PARTS for i in parts[part]]
        assert sorted(flat) == list(range(n))
        assert (
            len(parts["train"]) > len(parts["val"]) + len(parts["test1"]) + len(parts["test2"]) - 5
        )


def test_claim_texts_of_different_parts_never_coincide() -> None:
    for family, claims in FAMILIES.items():
        parts = make_cases.held_out(len(claims))
        texts = {p: {normalize(claims[i][1]) for i in parts[p]} for p in make_cases.PARTS}
        for a in make_cases.PARTS:
            for b in make_cases.PARTS:
                if a < b:
                    assert not texts[a] & texts[b], (family, a, b)
        assert len({normalize(t) for _, t in claims}) == len(claims), family


def test_styles_are_spread_over_the_parts() -> None:
    """Training sees every style; each test part (only two or three claims per family) at least two."""
    for family, claims in FAMILIES.items():
        parts = make_cases.held_out(len(claims))
        assert {claims[i][0] for i in parts["train"]} == {
            "standard",
            "banglish",
            "regional",
            "mixed",
        }, family
        for part in ("test1", "test2"):
            assert len({claims[i][0] for i in parts[part]}) >= 2, (family, part)


def test_case_generation_is_deterministic_and_part_specific() -> None:
    import random

    one = make_cases.make_case(random.Random(7), "test1", "SF1", "ai_b", 1)
    two = make_cases.make_case(random.Random(7), "test1", "SF1", "ai_b", 1)
    assert one == two
    story = one["story_key"]
    train_story = make_cases.make_case(random.Random(7), "train", "SF1", "ai_a", 1)["story_key"]
    assert story != train_story


def test_bank_subtypes_match_the_blueprint_table() -> None:
    assert sorted(make_cases.SUBTYPES) == sorted(validate_cases.SUBTYPE_LABEL)
    for subtype, (label, _) in make_cases.SUBTYPES.items():
        assert validate_cases.SUBTYPE_LABEL[subtype] == label


def test_dataset_hash_matches_what_the_model_was_trained_on() -> None:
    meta_path = REPO / "models" / "dispute_baseline_v1.meta.json"
    if not meta_path.exists():
        pytest.skip("run `make train-dispute` first")
    meta = json.loads(meta_path.read_text())
    for name in ("train", "validation"):
        digest = sha256((REPO / CFG["out_dir"] / f"{name}.jsonl").read_bytes()).hexdigest()
        assert meta["trained_on"][name]["sha256"] == digest, f"{name} changed since training"
