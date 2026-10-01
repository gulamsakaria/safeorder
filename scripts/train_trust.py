"""Train the seller trust model on generator v1 and save it with a metadata file.

Usage: PYTHONPATH=backend:. python -m scripts.train_trust
"""

import json
from datetime import UTC, datetime
from importlib import metadata

from app.config import load_config
from app.trust.dataset import REPO_ROOT, load_features, load_sellers, version_dir
from app.trust.model import train_model


def main() -> None:
    cfg = load_config()
    settings = cfg["trust_model"]
    features = load_features("v1")
    labels = load_sellers("v1").loc[features.index, "is_high_risk"]
    model, report = train_model(features, labels, cfg)

    models_dir = REPO_ROOT / cfg["paths"]["models_dir"]
    model_path = models_dir / f"{settings['version']}.joblib"
    model.save(model_path)
    manifest = json.loads((version_dir("v1") / "manifest.json").read_text())
    meta = {
        "version": settings["version"],
        "trained_at": datetime.now(UTC).date().isoformat(),
        "trained_on": {"generator": "v1", "files": manifest["files"], "seed": manifest["seed"]},
        "seed": settings["seed"],
        "feature_columns": model.feature_columns,
        "feature_medians": model.medians,
        "hyperparameters": settings["lightgbm"],
        "calibration": settings["calibration"],
        "monotone_increasing_risk": settings.get("monotone_increasing_risk", []),
        "split": settings["split"],
        "training": {k: v for k, v in report.items() if k != "split_seller_ids"},
        "libraries": {
            name: metadata.version(name) for name in ("lightgbm", "scikit-learn", "numpy", "pandas")
        },
        "note": "Trained on synthetic data only. Not validated on real data.",
    }
    meta_path = models_dir / f"{settings['version']}.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(json.dumps(meta["training"], indent=2))
    print(f"saved {model_path.relative_to(REPO_ROOT)} and {meta_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
