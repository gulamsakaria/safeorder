"""Baseline dispute classifier (BLUEPRINT.md Section 9.2): TF-IDF + logistic regression.

Word 1-2 grams plus character 2-5 grams over the text built by ``text_format.build_text``, a
class-balanced logistic regression, and probabilities calibrated (sigmoid) on the validation split.
It is a plain linear model: it cannot follow instructions in the text, only count words.
"""

from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from app.config import load_config
from app.disputes.classifier import CLASSES, validate_probabilities
from app.disputes.text_format import build_text

VERSION = "dispute_baseline_v1"


def case_text(case: dict[str, Any], cfg: dict[str, Any] | None = None) -> str:
    """The classifier input for one case record (raw case file fields)."""
    return build_text(
        courier_status=case["courier_status"],
        code_used=case["delivery_code_used"],
        amount_bdt=case["amount_bdt"],
        buyer_claim=case["buyer_claim"],
        seller_response=case["seller_response"],
        buyer_evidence=case["buyer_evidence"],
        seller_evidence=case["seller_evidence"],
        cfg=cfg,
    )


def _pipeline(settings: dict[str, Any]) -> Pipeline:
    word = TfidfVectorizer(
        analyzer="word", ngram_range=tuple(settings["word_ngrams"]), lowercase=True,
        sublinear_tf=True, max_features=settings["max_features_word"], token_pattern=r"(?u)\b\w+\b",
    )  # fmt: skip
    char = TfidfVectorizer(
        analyzer="char_wb", ngram_range=tuple(settings["char_ngrams"]), lowercase=True,
        sublinear_tf=True, max_features=settings["max_features_char"],
    )  # fmt: skip
    classifier = LogisticRegression(
        C=settings["C"], class_weight="balanced", max_iter=3000, random_state=settings["seed"]
    )
    return Pipeline(
        [("features", FeatureUnion([("word", word), ("char", char)])), ("clf", classifier)]
    )


class BaselineClassifier:
    """Calibrated TF-IDF + logistic regression. Implements ``DisputeClassifier``."""

    version = VERSION

    def __init__(self, model: Any, calibrated: bool, meta: dict[str, Any] | None = None) -> None:
        self.model = model
        self.calibrated = calibrated
        self.meta = meta or {}
        self.classes = [str(c) for c in model.classes_]
        if sorted(self.classes) != sorted(CLASSES):
            raise ValueError(f"model classes {self.classes} do not match {CLASSES}")

    def predict_proba_many(self, texts: list[str]) -> np.ndarray:
        """Probabilities in the order of ``CLASSES``, one row per text."""
        raw = self.model.predict_proba(texts)
        order = [self.classes.index(c) for c in CLASSES]
        return raw[:, order]

    def predict_proba(self, text: str) -> dict[str, float]:
        row = self.predict_proba_many([text])[0]
        total = float(row.sum())
        return validate_probabilities(
            {c: float(p) / total for c, p in zip(CLASSES, row, strict=True)}
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self.model, "calibrated": self.calibrated, "meta": self.meta}, path)

    @classmethod
    def load(cls, path: Path) -> "BaselineClassifier":
        blob = joblib.load(path)
        return cls(blob["model"], blob["calibrated"], blob.get("meta"))


def train_baseline(
    train: tuple[list[str], list[str]],
    calibration: tuple[list[str], list[str]] | None,
    cfg: dict[str, Any] | None = None,
) -> tuple[BaselineClassifier, BaselineClassifier]:
    """Fit on ``train``; calibrate on ``calibration``. Returns (calibrated, uncalibrated).

    The uncalibrated twin is kept only so the report can show what calibration changed. Which one
    is used is decided by the specification (calibrated), never by test results.
    """
    settings = (cfg or load_config())["dispute"]["baseline"]
    pipeline = _pipeline(settings)
    pipeline.fit(train[0], train[1])
    plain = BaselineClassifier(pipeline, calibrated=False)
    if calibration is None:
        return plain, plain
    calibrated = CalibratedClassifierCV(FrozenEstimator(pipeline), method="sigmoid")
    calibrated.fit(calibration[0], calibration[1])
    return BaselineClassifier(calibrated, calibrated=True), plain


def expected_calibration_error(probs: np.ndarray, truth: np.ndarray, bins: int = 10) -> float:
    """Top-label ECE: the gap between confidence and accuracy, averaged over confidence bins."""
    confidence = probs.max(axis=1)
    correct = (probs.argmax(axis=1) == truth).astype(float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for low, high in zip(edges[:-1], edges[1:], strict=True):
        mask = (confidence > low) & (confidence <= high)
        if mask.any():
            total += mask.mean() * abs(confidence[mask].mean() - correct[mask].mean())
    return float(total)


def log_loss(probs: np.ndarray, truth: np.ndarray) -> float:
    clipped = np.clip(probs[np.arange(len(truth)), truth], 1e-12, 1.0)
    return float(-np.mean(np.log(clipped)))
