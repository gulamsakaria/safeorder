"""Seller risk model (BLUEPRINT.md Section 9.1): calibrated LightGBM plus explainable reasons.

The model only estimates P(high risk). The score, the band and the warning rules stay in
``app/rules.py``. Reasons come from LightGBM's own per-feature contributions.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import train_test_split

from app import rules
from app.clock import clock, to_iso
from app.config import load_config
from app.enums import TrustBand
from app.trust.features import FEATURE_COLUMNS
from app.trust.reasons import Reason, build_reasons

PLATT_C = 1e6  # effectively unregularised logistic fit


def _sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-x))


@dataclass
class TrustResult:
    seller_id: str | None
    model_score: int  # always set; stored in trust_snapshot
    band: TrustBand
    limited_history: bool
    reasons: list[Reason]
    model_version: str
    generated_at: datetime
    probability: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def score(self) -> int | None:
        """Score shown to the buyer. Hidden behind the neutral band for limited history."""
        return None if self.band == TrustBand.LIMITED_HISTORY else self.model_score

    def to_api(self) -> dict[str, Any]:
        """Trust Check response (BLUEPRINT.md Section 7)."""
        return {
            "seller_id": self.seller_id,
            "score": self.score,
            "band": self.band.value,
            "limited_history": self.limited_history,
            "reasons": [r.to_api() for r in self.reasons],
            "model_version": self.model_version,
            "generated_at": to_iso(self.generated_at),
        }


class TrustModel:
    def __init__(
        self,
        booster: lgb.Booster,
        platt: tuple[float, float],
        feature_columns: list[str],
        medians: dict[str, float],
        version: str,
    ) -> None:
        self.booster = booster
        self.platt = platt
        self.feature_columns = feature_columns
        self.medians = medians
        self.version = version

    # ---- scoring -----------------------------------------------------------------------------

    def _matrix(self, features: pd.DataFrame) -> np.ndarray:
        return features[self.feature_columns].to_numpy(dtype=float)

    def raw_margin(self, matrix: np.ndarray) -> np.ndarray:
        return np.asarray(self.booster.predict(matrix, raw_score=True))

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        """Calibrated P(high risk) for every row."""
        a, b = self.platt
        return np.asarray(_sigmoid(a * self.raw_margin(self._matrix(features)) + b))

    def contributions(self, matrix: np.ndarray) -> np.ndarray:
        """Per-feature contributions in log-odds, without the bias column."""
        return np.asarray(self.booster.predict(matrix, pred_contrib=True))[:, :-1]

    def predict(
        self,
        features: Mapping[str, float | None],
        *,
        seller_id: str | None = None,
        order_count: int | None = None,
        generated_at: datetime | None = None,
        cfg: dict[str, Any] | None = None,
    ) -> TrustResult:
        """Trust Check for one seller. ``features`` maps feature names to values."""
        values = {
            c: (np.nan if features.get(c) is None else float(features[c]))  # type: ignore[arg-type]
            for c in self.feature_columns
        }
        matrix = np.array([[values[c] for c in self.feature_columns]], dtype=float)
        a, b = self.platt
        probability = float(_sigmoid(a * self.raw_margin(matrix)[0] + b))
        score = rules.score_from_probability(probability)
        age = values["account_age_days"]
        orders = int(order_count) if order_count is not None else 0
        band = rules.trust_band(score, age, orders, cfg)
        limited = rules.is_limited_history(age, orders, cfg)
        contributions = dict(zip(self.feature_columns, self.contributions(matrix)[0], strict=True))
        reasons = build_reasons(
            values, contributions, self.medians, score,
            limited_history=band == TrustBand.LIMITED_HISTORY, cfg=cfg,
        )  # fmt: skip
        return TrustResult(
            seller_id=seller_id,
            model_score=score,
            band=band,
            limited_history=limited,
            reasons=reasons,
            model_version=self.version,
            generated_at=generated_at or clock.now(),
            probability=probability,
        )

    # ---- persistence -------------------------------------------------------------------------

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model_string": self.booster.model_to_string(),
                "platt": self.platt,
                "feature_columns": self.feature_columns,
                "medians": self.medians,
                "version": self.version,
            },
            path,
        )

    @classmethod
    def load(cls, path: Path) -> "TrustModel":
        blob = joblib.load(path)
        return cls(
            lgb.Booster(model_str=blob["model_string"]),
            tuple(blob["platt"]),
            blob["feature_columns"],
            blob["medians"],
            blob["version"],
        )


# ---- training ------------------------------------------------------------------------------


def split_indices(
    labels: pd.Series, fractions: Mapping[str, float], seed: int
) -> dict[str, np.ndarray]:
    """Stratified train / validation / calibration split of positional indices."""
    positions = np.arange(len(labels))
    holdout = fractions["validation"] + fractions["calibration"]
    train, rest = train_test_split(
        positions, test_size=holdout, stratify=labels, random_state=seed, shuffle=True
    )
    share_cal = fractions["calibration"] / holdout
    valid, calib = train_test_split(
        rest, test_size=share_cal, stratify=labels.iloc[rest], random_state=seed, shuffle=True
    )
    return {"train": train, "validation": valid, "calibration": calib}


def train_model(
    features: pd.DataFrame, labels: pd.Series, cfg: dict[str, Any] | None = None
) -> tuple[TrustModel, dict[str, Any]]:
    """Train on generator v1 only. Returns the model and a small training report."""
    settings = (cfg or load_config())["trust_model"]
    seed = settings["seed"]
    parts = split_indices(labels, settings["split"], seed)
    x = features[FEATURE_COLUMNS]
    y = labels.to_numpy()

    params = dict(settings["lightgbm"])
    early_stopping = params.pop("early_stopping_rounds")
    classifier = lgb.LGBMClassifier(
        **params, random_state=seed, deterministic=True, force_row_wise=True, n_jobs=1, verbose=-1
    )
    classifier.fit(
        x.iloc[parts["train"]], y[parts["train"]],
        eval_X=x.iloc[parts["validation"]], eval_y=y[parts["validation"]],
        eval_metric="binary_logloss",
        callbacks=[lgb.early_stopping(early_stopping, verbose=False)],
    )  # fmt: skip
    booster = classifier.booster_

    calib_margin = booster.predict(x.iloc[parts["calibration"]].to_numpy(), raw_score=True)
    if settings["calibration"] != "platt":
        raise ValueError("only Platt scaling is implemented (see config trust_model.calibration)")
    platt_fit = LogisticRegression(C=PLATT_C).fit(
        np.asarray(calib_margin).reshape(-1, 1), y[parts["calibration"]]
    )
    platt = (float(platt_fit.coef_[0][0]), float(platt_fit.intercept_[0]))

    medians = {c: float(np.nanmedian(x.iloc[parts["train"]][c])) for c in FEATURE_COLUMNS}
    model = TrustModel(booster, platt, list(FEATURE_COLUMNS), medians, settings["version"])

    validation_probability = model.predict_proba(x.iloc[parts["validation"]])
    report = {
        "n_train": int(len(parts["train"])),
        "n_validation": int(len(parts["validation"])),
        "n_calibration": int(len(parts["calibration"])),
        "best_iteration": int(classifier.best_iteration_ or settings["lightgbm"]["n_estimators"]),
        "platt": {"slope": platt[0], "intercept": platt[1]},
        "validation_pr_auc": float(
            average_precision_score(y[parts["validation"]], validation_probability)
        ),
        "positive_rate_train": float(np.mean(y[parts["train"]])),
        "split_seller_ids": {k: features.index[v].tolist() for k, v in parts.items()},
    }
    if not math.isfinite(report["validation_pr_auc"]):
        raise ValueError("validation PR-AUC is not finite")
    return model, report
