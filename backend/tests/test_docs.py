"""Documentation set and secret scan (BLUEPRINT.md Step 14)."""

import pytest

from app.config import load_config
from scripts import build_docs, secret_scan, upload_hf

CFG = load_config()
DOCUMENTS = {
    "model_card": lambda: build_docs.model_card(CFG),
    "dataset_card": build_docs.dataset_card,
    "evaluation_protocol": lambda: build_docs.evaluation_protocol(CFG),
    "responsible_ai": lambda: build_docs.responsible_ai(CFG),
    "licence_register": build_docs.licence_register,
    "dispute_model_card": lambda: build_docs.dispute_model_card(CFG),
    "dispute_dataset_card": lambda: build_docs.dispute_dataset_card(CFG),
}


@pytest.mark.parametrize("name", DOCUMENTS)
def test_every_document_says_it_is_synthetic_and_not_validated(name: str) -> None:
    text = DOCUMENTS[name]()
    assert "synthetic" in text.lower()
    assert "not validated on real data" in text.lower()


@pytest.mark.parametrize("name", DOCUMENTS)
def test_documents_have_no_unfilled_placeholders(name: str) -> None:
    text = DOCUMENTS[name]()
    for bad in ("None%", "{", "}", "nan%", "NaN"):
        assert bad not in text, (name, bad)


def test_the_generated_files_in_docs_are_current() -> None:
    for name, build in {
        "model_card_trust.md": DOCUMENTS["model_card"],
        "dataset_card_synthetic_sellers.md": DOCUMENTS["dataset_card"],
        "evaluation_protocol.md": DOCUMENTS["evaluation_protocol"],
        "responsible_ai.md": DOCUMENTS["responsible_ai"],
        "model_card_dispute_classifier.md": DOCUMENTS["dispute_model_card"],
        "dataset_card_dispute_cases.md": DOCUMENTS["dispute_dataset_card"],
    }.items():
        assert (build_docs.DOCS / name).read_text(encoding="utf-8") == build(), (
            f"docs/{name} is stale: run `make docs`"
        )


def test_the_numbers_in_the_model_card_come_from_the_report() -> None:
    import json

    report = json.loads((build_docs.REPO / "reports" / "trust_eval.json").read_text())
    card = DOCUMENTS["model_card"]()
    pr_auc = report["test_v2"]["noisy_label"]["model"]["pr_auc"]
    assert f"{pr_auc:.3f}" in card


def test_secret_scan_finds_credentials_and_ignores_ordinary_text(tmp_path) -> None:
    bad = tmp_path / "bad.txt"
    bad.write_text("token = " + "hf_" + "a" * 34 + "\nplain line\n")
    key = tmp_path / "key.txt"
    key.write_text("-----BEGIN " + "RSA PRIVATE KEY-----\n")
    fine = tmp_path / "fine.md"
    fine.write_text("Set HF_TOKEN in your environment. KAGGLE_KEY=placeholder-proxy\n")
    found = {(p.name, kind) for p, _, kind in secret_scan.scan([bad, key, fine])}
    assert found == {("bad.txt", "Hugging Face token"), ("key.txt", "private key block")}


def test_the_repository_has_no_secrets() -> None:
    assert secret_scan.scan(secret_scan.tracked_files()) == []


def test_upload_script_has_no_way_to_make_a_repository_public() -> None:
    source = (build_docs.REPO / "scripts" / "upload_hf.py").read_text()
    assert "private=True" in source
    assert "private=False" not in source
    assert "--public" not in source
    assert upload_hf.MODEL_FILES


def test_dispute_documents_state_the_single_author_limit() -> None:
    for name in ("dispute_model_card", "dispute_dataset_card"):
        text = DOCUMENTS[name]().lower()
        assert "written by the ai assistant" in text or "written by the ai" in text
        assert "not" in text and "chatgpt" in text
    assert "no human has reviewed" in DOCUMENTS["dispute_dataset_card"]().lower()


# ---- pitch material and drafts ---------------------------------------------------------------

from scripts import build_pitch  # noqa: E402

PITCH = {
    "pitch/demo_script.md": build_pitch.demo_script,
    "pitch/pitch_outline.md": build_pitch.pitch_outline,
    "pitch/judge_questions.md": build_pitch.judge_questions,
    "drafts/logic_chain.md": build_pitch.logic_chain,
    "drafts/safe_order_terms.md": build_pitch.terms,
}
STATIC = {
    "drafts/interview_consent_note.md": build_pitch.consent_note,
    "drafts/team_agreement_outline.md": build_pitch.team_agreement,
    "drafts/regulatory_note.md": build_pitch.regulatory_note,
    "drafts/organiser_questions.md": build_pitch.organiser_questions,
}


def render(name: str) -> str:
    facts = build_pitch.Facts(CFG)
    if name in PITCH:
        return PITCH[name](facts)
    return STATIC[name]()


@pytest.mark.parametrize("name", [*PITCH, *STATIC])
def test_pitch_files_are_current_marked_as_drafts_and_complete(name: str) -> None:
    text = render(name)
    assert (build_pitch.DOCS / name).read_text(encoding="utf-8") == text, (
        f"docs/{name} is stale: run `make docs`"
    )
    assert "DRAFT" in text and "not legal advice" in text.lower()
    assert "{" not in text and "}" not in text and "None%" not in text


def test_pitch_numbers_come_from_the_reports_and_the_limits_are_stated() -> None:
    import json

    report = json.loads((build_pitch.REPO / "reports" / "dispute_eval_baseline.json").read_text())
    outline = render("pitch/pitch_outline.md")
    assert f"{report['splits']['test1']['macro_f1']:.2f}" in outline
    assert "written by an AI" in outline and "one author" in outline
    assert "not measured" in outline  # impact is not measured
    questions = render("pitch/judge_questions.md")
    assert "Who wrote the dispute cases" in questions and "AI assistant wrote them" in questions
    assert "not a defence" in questions
