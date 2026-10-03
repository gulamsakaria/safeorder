"""Settings and startup steps for running the whole app as one web service (for example a
Hugging Face Docker Space): environment overrides, serving the built frontend, seeding the demo.

Everything here is off by default, so local development and the tests behave as before.

Environment variables (all optional):
  SAFEORDER_SERVE_FRONTEND=1   serve the built frontend (web.dist_dir) from the same address as /api
  SAFEORDER_AUTOSEED=1         on start, reset the database and load the seven demo scenarios
  SAFEORDER_DEMO_CODE=...      /api/demo and /api/sim then need header X-Demo-Code = this value
  SAFEORDER_TRUST_PROXY=1      take the client address from X-Forwarded-For (only behind a proxy)
  SAFEORDER_RATE_LIMIT=N       requests per minute per client (0 = off)
  SAFEORDER_CORS_ORIGINS=a,b   allowed browser origins
"""

import copy
import logging
import os
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response

from app.api.errors import ApiError
from app.db import create_db, make_engine

logger = logging.getLogger("safeorder.deploy")
REPO_ROOT = Path(__file__).resolve().parents[2]
TRUE = ("1", "true", "yes", "on")


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in TRUE


def apply_env(config: dict[str, Any]) -> dict[str, Any]:
    """A copy of the configuration with the environment overrides applied."""
    cfg = copy.deepcopy(config)
    api = cfg["api"]
    if "SAFEORDER_RATE_LIMIT" in os.environ:
        api["rate_limit_per_minute"] = int(os.environ["SAFEORDER_RATE_LIMIT"])
    if os.environ.get("SAFEORDER_CORS_ORIGINS"):
        api["cors_origins"] = [o.strip() for o in os.environ["SAFEORDER_CORS_ORIGINS"].split(",")]
    if env_flag("SAFEORDER_TRUST_PROXY"):
        api["trust_proxy_headers"] = True
    return cfg


def install_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built frontend; unknown paths get index.html (the app uses client-side routes)."""
    dist = dist.resolve()
    index = dist / "index.html"
    if not index.is_file():
        raise FileNotFoundError(f"{index} not found: build the frontend first")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> Response:
        if path == "api" or path.startswith("api/"):
            raise ApiError(404, "NOT_FOUND", "not found")
        target = (dist / path).resolve()
        if path and target.is_file() and target.is_relative_to(dist):
            immutable = target.parent.name == "assets"  # build output is content-hashed
            headers = {"Cache-Control": "public, max-age=31536000, immutable"} if immutable else {}
            return FileResponse(target, headers=headers)
        return FileResponse(index)


def seed_demo(app: FastAPI) -> None:
    """Reset the database and load the demo scenarios. Failure is logged, not fatal."""
    from app.demo_scenarios import load_demo_scenarios
    from app.seed import reset_and_load
    from app.trust.model import TrustModel

    cfg = app.state.cfg
    try:
        engine = app.state.engine
        if engine is None:
            engine = app.state.engine = make_engine()
        create_db(engine)
        loaded = reset_and_load(engine, "demo", cfg)
        path = REPO_ROOT / cfg["paths"]["models_dir"] / f"{cfg['trust_model']['version']}.joblib"
        model = app.state.trust_model or TrustModel.load(path)
        app.state.trust_model = model
        scenarios = load_demo_scenarios(engine, model, app.state.classifier, cfg)
        logger.info("demo seeded: %s, %d scenarios", loaded, len(scenarios))
    except Exception:  # the server should still come up so the problem can be seen
        logger.exception("demo seeding failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if env_flag("SAFEORDER_AUTOSEED"):
        if env_flag("SAFEORDER_AUTOSEED_BACKGROUND"):
            # Seeding can take minutes on a small free instance; the server must open its port
            # first or the host (Render) gives up with "no open ports detected".
            threading.Thread(target=seed_demo, args=(app,), name="seed-demo", daemon=True).start()
        else:
            seed_demo(app)
    yield
