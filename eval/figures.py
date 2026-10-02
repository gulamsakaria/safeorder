"""Figures for the slides and the model cards, drawn only from reports/summary.json."""

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
BLUE, ORANGE = "#2a78d6", "#eb6834"  # blue = the model, orange = the simple baseline
DPI = 160


def _style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": GRID,
        "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "font.size": 11,
        "axes.axisbelow": True,
    })  # fmt: skip


def _save(fig: Any, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return path


def trust_comparison(summary: dict[str, Any], out: Path) -> Path:
    test = summary["trust"]["test_v2"]["noisy_label"]
    target = summary["trust"]["target_false_positive_rate"]
    model, base = test["model"], test["age_score_baseline"]
    groups = ["PR-AUC", f"Recall at {target:.0%} false alarms"]
    model_values = [model["pr_auc"], model["recall_at_target_fpr"]["recall"]]
    base_values = [base["pr_auc"], base["recall_at_target_fpr"]["recall"]]
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    width = 0.36
    for i, (m, b) in enumerate(zip(model_values, base_values, strict=True)):
        ax.bar(i - width / 2, m, width, color=BLUE, label="Trust model" if i == 0 else None)
        ax.bar(i + width / 2, b, width, color=ORANGE, label="Account-age score" if i == 0 else None)
        ax.text(i - width / 2, m + 0.015, f"{m:.2f}", ha="center", color=INK)
        ax.text(i + width / 2, b + 0.015, f"{b:.2f}", ha="center", color=INK)
    ax.set_xticks(range(len(groups)), groups)
    ax.set_ylim(0, 1.22)
    ax.set_title("Held-out synthetic test (generator v2)", loc="left", fontsize=12)
    ax.legend(frameon=False, loc="upper center", ncol=2)
    fig.text(0.01, -0.04, "Synthetic data, not validated on real data.", color=MUTED, fontsize=9)
    return _save(fig, out / "trust_comparison.png")


def calibration(summary: dict[str, Any], out: Path) -> Path:
    bins = summary["trust"]["test_v2"]["noisy_label"]["calibration"]["bins"]
    ece = summary["trust"]["test_v2"]["noisy_label"]["calibration"]["ece"]
    fig, ax = plt.subplots(figsize=(4.6, 4.6))
    ax.plot([0, 1], [0, 1], color=MUTED, linestyle="--", linewidth=1, label="perfect")
    xs = [b["mean_predicted"] for b in bins if b["n"]]
    ys = [b["observed_rate"] for b in bins if b["n"]]
    ax.plot(xs, ys, color=BLUE, marker="o", linewidth=2, label="Trust model")
    ax.set_xlabel("Predicted risk")
    ax.set_ylabel("Observed share of high-risk sellers")
    ax.set_title(f"Calibration on v2 (ECE {ece:.3f})", loc="left", fontsize=12)
    ax.legend(frameon=False)
    return _save(fig, out / "calibration.png")


def policy_recall(summary: dict[str, Any], out: Path) -> Path:
    policies = summary["fairness"]["policies"]
    names = ["no_limited_history_band", "override_default", "blueprint_literal"]
    labels = ["No limited-history band", "Configured override", "Blueprint literal"]
    values = [policies[n]["recall_high_risk_overall"] for n in names]
    colours = [MUTED, BLUE, MUTED]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    bars = ax.barh(labels, values, color=colours)
    for bar, v in zip(bars, values, strict=True):
        ax.text(v + 0.01, bar.get_y() + bar.get_height() / 2, f"{v:.2f}", va="center", color=INK)
    ax.set_xlim(0, 1.1)
    ax.set_xlabel("Recall of high-risk sellers (v2)")
    ax.set_title("Cost of protecting honest new sellers", loc="left", fontsize=12)
    return _save(fig, out / "policy_recall.png")


def dispute_f1(summary: dict[str, Any], out: Path) -> Path:
    splits = summary["dispute_classifier"]["baseline"]["splits"]
    names = [n for n in ("validation", "test1", "test2") if n in splits]
    labels = {
        "validation": "Validation\n(used for calibration)",
        "test1": "Test 1",
        "test2": "Test 2",
    }
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    width = 0.36
    for i, name in enumerate(names):
        every, story = splits[name]["macro_f1"], splits[name]["story_level"]["macro_f1"]
        ax.bar(i - width / 2, every, width, color=BLUE, label="All cases" if i == 0 else None)
        ax.bar(
            i + width / 2,
            story,
            width,
            color=ORANGE,
            label="One case per story" if i == 0 else None,
        )
        ax.text(i - width / 2, every + 0.015, f"{every:.2f}", ha="center", color=INK)
        ax.text(i + width / 2, story + 0.015, f"{story:.2f}", ha="center", color=INK)
    ax.set_xticks(range(len(names)), [labels[n] for n in names])
    ax.set_ylim(0, 1.22)
    ax.set_ylabel("Macro-F1")
    ax.set_title("Dispute classifier (assistant-written cases)", loc="left", fontsize=12)
    ax.legend(frameon=False, loc="upper center", ncol=2)
    fig.text(
        0.01,
        -0.04,
        "Synthetic cases from one author, not validated on real data.",
        color=MUTED,
        fontsize=9,
    )
    return _save(fig, out / "dispute_f1.png")


def dispute_confusion(summary: dict[str, Any], out: Path) -> Path:
    block = summary["dispute_classifier"]["baseline"]["splits"]["test1"]["confusion_matrix"]
    matrix, labels = block["rows_true_columns_predicted"], block["labels"]
    short = ["Seller fault", "Buyer false claim", "Courier issue", "Insufficient evidence"]
    fig, ax = plt.subplots(figsize=(5.6, 4.8))
    ax.imshow(matrix, cmap="Blues")
    ax.grid(False)
    ax.set_xticks(range(len(labels)), short, rotation=25, ha="right")
    ax.set_yticks(range(len(labels)), short)
    peak = max(max(row) for row in matrix)
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            ax.text(
                j,
                i,
                str(value),
                ha="center",
                va="center",
                color="white" if value > peak / 2 else INK,
            )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Test 1 confusion matrix", loc="left", fontsize=12)
    return _save(fig, out / "dispute_confusion_test1.png")


def make_all(summary: dict[str, Any], out: Path) -> list[Path]:
    """Draw every figure whose data exists; nothing is drawn for a section that is not measured."""
    _style()
    written: list[Path] = []
    if summary["trust"].get("status") == "measured":
        written += [trust_comparison(summary, out), calibration(summary, out)]
    if summary["fairness"].get("status") == "measured":
        written.append(policy_recall(summary, out))
    if summary["dispute_classifier"].get("status") == "measured":
        written += [dispute_f1(summary, out), dispute_confusion(summary, out)]
    return written
