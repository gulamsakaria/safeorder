"""FastAPI application (BLUEPRINT.md Section 7).

``create_app`` accepts a database engine, a trust model and a dispute classifier so tests can
inject their own. When they are not given, the engine and the trust model are created on first
use, and the dispute classifier is loaded from the trained model (see Step 6).
"""

import os
from typing import Any

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from app.api import accounts, admin, analyst, demo, disputes, metrics, orders, sim, trust
from app.api.deps import require_admin_if_protected
from app.api.errors import install_error_handlers
from app.config import load_config
from app.deploy import REPO_ROOT, apply_env, env_flag, install_frontend, lifespan
from app.disputes.classifier import DisputeClassifier
from app.schemas import ErrorOut
from app.security import install as install_security
from app.trust.model import TrustModel

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorOut, "description": "Bad request, for example a wrong delivery code"},
    404: {"model": ErrorOut, "description": "Not found"},
    409: {"model": ErrorOut, "description": "Not allowed in the current state"},
    413: {"model": ErrorOut, "description": "Request body too large"},
    422: {"model": ErrorOut, "description": "Validation error"},
    429: {"model": ErrorOut, "description": "Too many requests"},
    503: {"model": ErrorOut, "description": "A model is not available"},
}


def create_app(
    engine: Engine | None = None,
    trust_model: TrustModel | None = None,
    classifier: DisputeClassifier | None = None,
    cfg: dict[str, Any] | None = None,
    serve_frontend: bool | None = None,
) -> FastAPI:
    config = cfg or apply_env(load_config())
    app = FastAPI(title=config["project"]["name"], version="1.0", lifespan=lifespan)
    app.state.cfg = config
    app.state.demo_code = os.environ.get("SAFEORDER_DEMO_CODE") or None
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
    install_security(app, config["api"], config["wallet"]["upload_max_body_bytes"])

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/db", include_in_schema=False)
    def health_db() -> dict[str, Any]:
        """Which database the service uses. A SQLite file inside a free host is wiped at every
        restart, so accounts survive only with DATABASE_URL set to a hosted Postgres."""
        from app.db import database_url_from_env

        url = database_url_from_env()
        kind = "sqlite"
        if url is not None and not url.startswith("sqlite"):
            kind = url.split(":")[0].split("+")[0]
        return {
            "database": kind,
            "keeps_data": kind != "sqlite",
            "persist_mode": config["api"].get("persist", False),
        }

    prefix = config["api"]["base_path"]
    for module in (trust, orders, sim, disputes, metrics, demo, accounts, admin):
        app.include_router(module.router, prefix=prefix, responses=ERROR_RESPONSES)
    # the analyst console is for admins once accounts are on (api.protect_admin)
    app.include_router(
        analyst.router,
        prefix=prefix,
        responses=ERROR_RESPONSES,
        dependencies=[Depends(require_admin_if_protected)],
    )
    if (
        env_flag("SAFEORDER_SERVE_FRONTEND") if serve_frontend is None else serve_frontend
    ):  # last: its catch-all route must not shadow the API
        dist = REPO_ROOT / config["web"]["dist_dir"]
        if not (dist / "index.html").is_file():
            # a downloaded copy of the repository has no build output (frontend/dist is not in
            # git) but ships the ready-built website in site/, so it still opens in the browser
            dist = REPO_ROOT / "site"
        install_frontend(app, dist)
    return app


app = create_app()
