"""Evaluate the trust model on the held-out generator v2 (BLUEPRINT.md Section 10).

Usage: PYTHONPATH=backend:. python -m eval.trust_eval
Writes reports/trust_eval.json. Nothing here is tuned on v2.
"""

import copy
import json
import time
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score, roc_curve

from app import rules
from app.config import load_config
from app.enums import TrustBand
from app.trust.dataset import REPO_ROOT, load_features, load_sellers
from app.trust.model import TrustModel, split_indices

HIGH_RISK_ARCHETYPES = ("fake_burst", "slow_scammer", "collusive_ring")
HONEST_COHORTS = ("honest_established", "honest_new", "chronic_poor_service")
MS_PER_S = 1_000.0
PERCENTILE_95 = 95


def recall_at_fpr(y: np.ndarray, score: np.ndarray, target_fpr: float) -> dict[str, float]:
    """Best recall reachable while the false-positive rate stays at or under the target."""
    fpr, tpr, thresholds = roc_curve(y, score)
    ok = fpr <= target_fpr
    best = int(np.argmax(np.where(ok, tpr, -1.0)))
    return {
        "recall": float(tpr[best]),
        "false_positive_rate": float(fpr[best]),
        "threshold": float(thresholds[best]),
    }


def ranking_metrics(y: np.ndarray, score: np.ndarray, target_fpr: float) -> dict[str, Any]:
    return {
        "pr_auc": float(average_precision_score(y, score)),
        "roc_auc": float(roc_auc_score(y, score)),
        "recall_at_target_fpr": recall_at_fpr(y, score, target_fpr),
        "positives": int(y.sum()),
        "n": int(len(y)),
    }


def age_rule_point(y: np.ndarray, age: np.ndarray, max_age_days: float) -> dict[str, float]:
    """The simple baseline rule: account age under 14 days means high risk."""
    flagged = age < max_age_days
    tp = float((flagged & (y == 1)).sum())
    fp = float((flagged & (y == 0)).sum())
    return {
        "recall": tp / max(1.0, float((y == 1).sum())),
        "false_positive_rate": fp / max(1.0, float((y == 0).sum())),
        "precision": tp / max(1.0, tp + fp),
        "flagged_share": float(flagged.mean()),
    }


def calibration(y: np.ndarray, p: np.ndarray, n_bins: int) -> dict[str, Any]:
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    index = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    bins, ece = [], 0.0
    for b in range(n_bins):
        mask = index == b
        if not mask.any():
            continue
        predicted, observed = float(p[mask].mean()), float(y[mask].mean())
        ece += mask.mean() * abs(predicted - observed)
        bins.append(
            {"bin": b, "n": int(mask.sum()), "mean_predicted": predicted, "observed_rate": observed}
        )
    return {"brier": float(brier_score_loss(y, p)), "ece": float(ece), "bins": bins}


def policy_table(
    sellers: pd.DataFrame, features: pd.DataFrame, score: np.ndarray, cfg: dict[str, Any]
) -> dict[str, Any]:
    """Compare three ways of showing bands: none, literal blueprint, and the override rule."""
    literal = copy.deepcopy(cfg)
    literal["rules"]["trust"]["limited_history_override_max_score"] = None
    ages = features["account_age_days"].to_numpy()
    orders = features["orders_total"].to_numpy()
    archetype = sellers["archetype"].to_numpy()

    def bands(policy: str) -> np.ndarray:
        out = []
        for s, age, n in zip(score, ages, orders, strict=True):
            if policy == "no_limited_history_band":
                out.append(rules.band_for_score(int(s), cfg))
            elif policy == "blueprint_literal":
                out.append(rules.trust_band(int(s), age, int(n), literal))
            else:
                out.append(rules.trust_band(int(s), age, int(n), cfg))
        return np.array([b.value for b in out])

    table: dict[str, Any] = {}
    for policy in ("no_limited_history_band", "blueprint_literal", "override_default"):
        band = bands(policy)
        flagged = band == TrustBand.HIGH_RISK.value
        risky = np.isin(archetype, HIGH_RISK_ARCHETYPES)
        entry: dict[str, Any] = {
            "false_positive_rate": {},
            "limited_history_share": {},
            "recall_by_archetype": {},
        }
        for cohort in HONEST_COHORTS:
            mask = archetype == cohort
            entry["false_positive_rate"][cohort] = float(flagged[mask].mean())
            entry["limited_history_share"][cohort] = float(
                (band[mask] == TrustBand.LIMITED_HISTORY.value).mean()
            )
        for name in HIGH_RISK_ARCHETYPES:
            entry["recall_by_archetype"][name] = float(flagged[archetype == name].mean())
        entry["recall_high_risk_overall"] = float(flagged[risky].mean())
        entry["precision_of_high_risk_band"] = (
            float(risky[flagged].mean()) if flagged.any() else None
        )
        entry["band_counts"] = {b: int((band == b).sum()) for b in sorted(set(band))}
        table[policy] = entry
    return table


def reasons_and_latency(
    model: TrustModel, features: pd.DataFrame, cfg: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    settings = cfg["trust_model"]
    counts, timings = [], []
    rows = features.to_dict(orient="index")
    for position, (seller_id, row) in enumerate(rows.items()):
        values = {c: (None if pd.isna(row[c]) else row[c]) for c in model.feature_columns}
        start = time.perf_counter()
        result = model.predict(
            values, seller_id=seller_id, order_count=int(row["orders_total"]), cfg=cfg
        )
        elapsed = time.perf_counter() - start
        counts.append(len(result.reasons))
        if position < settings["eval"]["latency_samples"]:
            timings.append(elapsed * MS_PER_S)
    low, high = settings["reasons"]["min"], settings["reasons"]["max"]
    counts_arr = np.array(counts)
    warm = np.array(timings[1:] or timings)  # the first call includes one-off warm-up
    budget = settings["latency_budget_ms"]
    reasons = {
        "sellers_checked": len(counts),
        "min_reasons": int(counts_arr.min()),
        "max_reasons": int(counts_arr.max()),
        "all_within_range": bool(((counts_arr >= low) & (counts_arr <= high)).all()),
    }
    latency = {
        "samples": int(len(warm)),
        "mean_ms": float(warm.mean()),
        "p95_ms": float(np.percentile(warm, PERCENTILE_95)),
        "max_ms": float(warm.max()),
        "budget_ms": budget,
        "within_budget": bool(np.percentile(warm, PERCENTILE_95) < budget),
    }
    return reasons, latency


def main() -> None:
    cfg = load_config()
    settings = cfg["trust_model"]
    target = settings["eval"]["target_fpr"]
    model = TrustModel.load(
        REPO_ROOT / cfg["paths"]["models_dir"] / f"{settings['version']}.joblib"
    )

    f1, f2 = load_features("v1"), load_features("v2")
    s1, s2 = load_sellers("v1").loc[f1.index], load_sellers("v2").loc[f2.index]
    max_age = cfg["rules"]["trust"]["limited_history_max_age_days"]

    def evaluate(features: pd.DataFrame, sellers: pd.DataFrame) -> dict[str, Any]:
        probability = model.predict_proba(features)
        age = features["account_age_days"].to_numpy()
        out = {}
        for label_name, y in (
            ("noisy_label", sellers["is_high_risk"].to_numpy()),
            ("clean_label", sellers["archetype"].isin(HIGH_RISK_ARCHETYPES).astype(int).to_numpy()),
        ):
            out[label_name] = {
                "model": ranking_metrics(y, probability, target),
                "age_score_baseline": ranking_metrics(y, -age, target),
                "age_rule_baseline": age_rule_point(y, age, max_age),
                "calibration": calibration(y, probability, settings["eval"]["calibration_bins"]),
            }
        return out

    parts = split_indices(s1["is_high_risk"], settings["split"], settings["seed"])
    validation_ids = f1.index[parts["validation"]]
    test_probability = model.predict_proba(f2)
    score = np.array([rules.score_from_probability(float(p)) for p in test_probability])
    reasons, latency = reasons_and_latency(model, f2, cfg)

    report = {
        "model_version": model.version,
        "note": (
            "Synthetic data only; not validated on real data. The noisy label is the dataset's "
            "is_high_risk (about 4% flipped at random); the clean label is archetype-based and "
            "easier, so treat it as a diagnostic, not a headline."
        ),
        "target_false_positive_rate": target,
        "validation_v1_holdout": evaluate(f1.loc[validation_ids], s1.loc[validation_ids]),
        "test_v2": evaluate(f2, s2),
        "fairness_and_policy_v2": policy_table(s2, f2, score, cfg),
        "reasons_v2": reasons,
        "latency": latency,
    }
    path = REPO_ROOT / cfg["paths"]["reports_dir"] / "trust_eval.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: report[k] for k in ("reasons_v2", "latency")}, indent=2))
    test = report["test_v2"]["noisy_label"]
    print(
        "v2 noisy label  model :",
        json.dumps(test["model"]["recall_at_target_fpr"]),
        "PR-AUC",
        round(test["model"]["pr_auc"], 3),
    )
    print(
        "v2 noisy label  age   :",
        json.dumps(test["age_rule_baseline"]),
        "| age-score PR-AUC",
        round(test["age_score_baseline"]["pr_auc"], 3),
    )
    print(f"wrote {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
