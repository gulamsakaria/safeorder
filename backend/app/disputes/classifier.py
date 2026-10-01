"""Interface of the 4-class dispute classifier.

The real model (TF-IDF + logistic regression, BLUEPRINT.md Step 6) is trained once the dispute
cases are available. Until then ``load_classifier`` raises ``ClassifierNotAvailable`` rather than
returning a stand-in, so no screen can show invented probabilities.
"""

import math
from typing import Protocol

from app.enums import DisputeClass

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


def load_classifier() -> DisputeClassifier:
    raise ClassifierNotAvailable(
        "no trained dispute classifier yet: add the dispute cases (Step 5) and train it (Step 6)"
    )
