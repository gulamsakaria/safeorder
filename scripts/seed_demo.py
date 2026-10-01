"""Reset the database and load the seven demo scenarios (BLUEPRINT.md Section 12.2).

Usage (repository root): PYTHONPATH=backend:. python -m scripts.seed_demo
Needs `make data` and `make train` first. Prints the ids the presenter uses.
"""

from pathlib import Path

from app.config import load_config
from app.db import create_db, make_engine
from app.demo_scenarios import load_demo_scenarios
from app.seed import reset_and_load
from app.trust.model import TrustModel

REPO = Path(__file__).resolve().parents[1]


def main() -> None:
    cfg = load_config()
    engine = make_engine()
    create_db(engine)
    loaded = reset_and_load(engine, "demo", cfg)
    model = TrustModel.load(
        REPO / cfg["paths"]["models_dir"] / f"{cfg['trust_model']['version']}.joblib"
    )
    scenarios = load_demo_scenarios(engine, model, None, cfg)
    print(f"loaded {loaded['sellers']} sellers and {loaded['buyers']} buyers")
    for s in scenarios:
        ids = ", ".join(
            f"{k}={v}"
            for k, v in s.items()
            if k in ("seller_id", "buyer_id", "order_id", "dispute_id", "delivery_code") and v
        )
        analysis = f" [analysis: {s['analysis']}]" if s["analysis"] else ""
        print(f"{s['number']}. {s['key']}: {ids}{analysis}\n   {s['detail']}")


if __name__ == "__main__":
    main()
