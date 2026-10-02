"""Interface of the 4-class dispute classifier.

The real model (TF-IDF + logistic regression, BLUEPRINT.md Step 6) lives in ``baseline.py``. When
its file is missing ``load_classifier`` raises ``ClassifierNotAvailable`` rather than returning a
stand-in, so no screen can show invented probabilities.
"""

import math
from pathlib import Path
from typing import Protocol

from app.enums import DisputeClass

REPO_ROOT = Path(__file__).resolve().parents[3]

CLASSES: tuple[str, ...] = tuple(c.value for c in DisputeClass)
PROBABILITY_TOLERANCE = 1e-6


class ClassifierNotAvailable(RuntimeError):
    pass


class DisputeClassifier(Protocol):
    version: str

    def predict_proba(self, text: str) -> dict[str, float]:
        """Probability for each of the four classes, summing to 1."""
        ...


def validate_probabilities(probs: dict[str, float]) -> dict[str, float]:
    if set(probs) != set(CLASSES):
        raise ValueError(f"class probabilities must cover exactly {CLASSES}")
    if any((not math.isfinite(p)) or p < 0 for p in probs.values()):
        raise ValueError("class probabilities must be finite and non-negative")
    if abs(sum(probs.values()) - 1.0) > PROBABILITY_TOLERANCE:
        raise ValueError("class probabilities must sum to 1")
    return {c: float(probs[c]) for c in CLASSES}


def top_class(probs: dict[str, float]) -> tuple[str, float]:
    """Most likely class; ties go to the class listed first in ``CLASSES``."""
    best = max(CLASSES, key=lambda c: (probs[c], -CLASSES.index(c)))
    return best, probs[best]


_LOADED: dict[str, DisputeClassifier] = {}


def model_path(cfg: dict | None = None) -> Path:
    from app.config import load_config

    config = cfg or load_config()
    return REPO_ROOT / config["paths"]["models_dir"] / "dispute_baseline_v1.joblib"


def load_classifier() -> DisputeClassifier:
    """The trained classifier chosen by ``dispute.model`` in the config (loaded once per process).

    Raises ``ClassifierNotAvailable`` when the model file does not exist or the chosen model type
    is not implemented, so no screen can ever show invented probabilities.
    """
    from app.config import load_config

    config = load_config()
    kind = config["dispute"]["model"]
    if kind != "baseline":
        raise ClassifierNotAvailable(f"dispute.model={kind!r} is not implemented, use 'baseline'")
    path = model_path(config)
    if not path.exists():
        raise ClassifierNotAvailable(
            f"no trained dispute classifier at {path.name}: run `make cases train-dispute`"
        )
    key = str(path)
    if key not in _LOADED:
        from app.disputes.baseline import BaselineClassifier

        _LOADED[key] = BaselineClassifier.load(path)
    return _LOADED[key]
