"""Train the baseline dispute classifier (BLUEPRINT.md Step 6).

Usage (repository root): PYTHONPATH=backend:. python -m scripts.train_dispute
Needs data/cases/train.jsonl and validation.jsonl (run `make cases` first). Fits on train,
calibrates on validation, saves models/dispute_baseline_v1.joblib and its .meta.json.
"""

import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from importlib import metadata
from pathlib import Path

from app.config import load_config
from app.disputes.baseline import VERSION, case_text, train_baseline

REPO = Path(__file__).resolve().parents[1]


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> int:
    cfg = load_config()
    out = REPO / cfg["dispute"]["cases"]["out_dir"]
    files = {name: out / f"{name}.jsonl" for name in ("train", "validation")}
    missing = [str(p.relative_to(REPO)) for p in files.values() if not p.exists()]
    if missing:
        print(f"missing {', '.join(missing)}: run `make cases` first")
        return 1
    train, validation = read(files["train"]), read(files["validation"])
    if not train or not validation:
        print("the train and validation splits must not be empty")
        return 1

    def prepare(rows: list[dict]) -> tuple[list[str], list[str]]:
        return [case_text(r, cfg) for r in rows], [r["label"] for r in rows]

    calibrated, _ = train_baseline(prepare(train), prepare(validation), cfg)
    models_dir = REPO / cfg["paths"]["models_dir"]
    path = models_dir / f"{VERSION}.joblib"
    meta = {
        "version": VERSION,
        "trained_at": datetime.now(UTC).date().isoformat(),
        "algorithm": "TF-IDF (word + char n-grams) + logistic regression, sigmoid calibration",
        "hyperparameters": cfg["dispute"]["baseline"],
        "calibration": "sigmoid, fitted on the validation split",
        "trained_on": {
            name: {"rows": len(rows), "sha256": sha256(files[name].read_bytes()).hexdigest()}
            for name, rows in (("train", train), ("validation", validation))
        },
        "data_provenance": (
            "Cases written by the Claude assistant (see raw/PROVENANCE.md), not by ChatGPT, "
            "Gemini or the team. Not validated on real data."
        ),
        "classes": calibrated.classes,
        "libraries": {n: metadata.version(n) for n in ("scikit-learn", "numpy", "joblib")},
        "note": "Trained on synthetic, assistant-written cases only. Not validated on real data.",
    }
    calibrated.meta = meta
    calibrated.save(path)
    (models_dir / f"{VERSION}.meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n"
    )
    print(f"trained on {len(train)} cases, calibrated on {len(validation)}")
    print(f"saved {path.relative_to(REPO)} and its meta file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
