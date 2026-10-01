"""FastAPI application (BLUEPRINT.md Section 7).

``create_app`` accepts a database engine, a trust model and a dispute classifier so tests can
inject their own. When they are not given, the engine and the trust model are created on first
use, and the dispute classifier is loaded from the trained model (see Step 6).
"""

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from app.api import analyst, demo, disputes, metrics, orders, sim, trust
from app.api.errors import install_error_handlers
from app.config import load_config
from app.disputes.classifier import DisputeClassifier
from app.trust.model import TrustModel


def create_app(
    engine: Engine | None = None,
    trust_model: TrustModel | None = None,
    classifier: DisputeClassifier | None = None,
    cfg: dict[str, Any] | None = None,
) -> FastAPI:
    config = cfg or load_config()
    app = FastAPI(title=config["project"]["name"], version="1.0")
    app.state.cfg = config
    app.state.engine = engine
    app.state.trust_model = trust_model
    app.state.classifier = classifier

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config["api"]["cors_origins"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    prefix = config["api"]["base_path"]
    for module in (trust, orders, sim, disputes, analyst, metrics, demo):
        app.include_router(module.router, prefix=prefix)
    return app


app = create_app()
