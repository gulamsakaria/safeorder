"""The static site (no backend): exported data and built files match the models and reports."""

import json
import zipfile
from pathlib import Path

import pytest

from app.config import load_config
from app.disputes import classifier as clf
from app.disputes.baseline import BaselineClassifier, case_text
from app.trust.model import TrustModel
from scripts import export_static

REPO = Path(__file__).resolve().parents[2]
ENGINE = REPO / "frontend" / "public" / "engine"
SITE = REPO / "site"
CFG = load_config()


def read(name: str) -> dict:
    return json.loads((ENGINE / name).read_text(encoding="utf-8"))


def test_the_summary_shown_by_the_static_metrics_page_is_the_current_report() -> None:
    assert (ENGINE / "summary.json").read_text(encoding="utf-8") == (
        REPO / "reports" / "summary.json"
    ).read_text(encoding="utf-8"), "run `make static-data` after `make eval`"


def test_exported_trust_model_matches_the_trained_model() -> None:
    model = TrustModel.load(REPO / "models" / "trust_v1.joblib")
    data = read("trust_model.json")
    assert data["feature_columns"] == model.feature_columns
    assert data["version"] == model.version
    assert data["platt"] == pytest.approx(list(model.platt))
    assert len(data["trees"]) == model.booster.num_trees()


def test_exported_classifier_reproduces_the_trained_model() -> None:
    model = BaselineClassifier.load(REPO / "models" / "dispute_baseline_v1.joblib")
    assert read("classifier.json")["classes"] == list(clf.CLASSES)
    rows = (
        (REPO / CFG["dispute"]["cases"]["out_dir"] / "test2.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[:40]
    )
    texts = [case_text(json.loads(r), CFG) for r in rows]
    gap = abs(
        export_static.reconstruct_probabilities(model, texts) - model.predict_proba_many(texts)
    ).max()
    assert gap < 1e-9


def test_all_synthetic_sellers_and_the_demo_picks_are_exported() -> None:
    sellers = read("sellers.json")
    assert len(sellers["sellers"]) == 3000
    ids = {row[0] for row in sellers["sellers"]}
    picks = read("scenarios.json")["picks"]
    assert set(picks.values()) <= ids
    assert all(len(row) == 5 + len(sellers["feature_columns"]) for row in sellers["sellers"])


def test_the_parity_fixtures_cover_trust_classifier_analyzer_and_injection() -> None:
    fixtures = json.loads(
        (REPO / "frontend" / "src" / "engine" / "fixtures" / "parity.json").read_text(
            encoding="utf-8"
        )
    )
    assert {k: len(v) > 40 for k, v in fixtures.items()} == {
        "trust": True, "classifier": True, "analyzer": True, "injection": True,
    }  # fmt: skip


def test_the_built_site_is_current_and_complete() -> None:
    if not SITE.exists():
        pytest.skip("run `make static-site` first")
    assert (SITE / "index.html").exists() and (SITE / ".htaccess").exists()
    for path in ENGINE.glob("*.json"):
        assert (SITE / "engine" / path.name).read_bytes() == path.read_bytes(), (
            f"site/engine/{path.name} is stale"
        )
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert 'src="./assets/' in html  # relative paths: works in any folder or sub-domain
    assert "localhost:8000" not in "".join(
        p.read_text(encoding="utf-8", errors="ignore") for p in (SITE / "assets").glob("*.js")
    )


def test_the_zip_holds_the_site_and_nothing_secret() -> None:
    archive = REPO / "site.zip"
    if not archive.exists():
        pytest.skip("run `make static-site` first")
    with zipfile.ZipFile(archive) as z:
        names = set(z.namelist())
        assert {
            "index.html",
            ".htaccess",
            "engine/classifier.json",
            "engine/trust_model.json",
        } <= names
        assert not any(n.endswith((".env", ".py", ".joblib", ".db")) for n in names)
        for name in names:
            if not name.endswith("/"):
                assert z.read(name) == (SITE / name).read_bytes(), f"site.zip is stale: {name}"
