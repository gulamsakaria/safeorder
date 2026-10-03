"""Shared request dependencies: database session, models and configuration."""

import hmac
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import Depends, Request
from sqlalchemy import Engine
from sqlmodel import Session

from app.api.errors import ApiError, ModelUnavailable
from app.config import load_config
from app.db import create_db, make_engine
from app.disputes.classifier import DisputeClassifier, load_classifier
from app.trust.model import TrustModel

REPO_ROOT = Path(__file__).resolve().parents[3]
_LOCK = threading.Lock()


def get_config(request: Request) -> dict[str, Any]:
    return getattr(request.app.state, "cfg", None) or load_config()


def get_engine(request: Request) -> Engine:
    state = request.app.state
    if getattr(state, "engine", None) is None:
        with _LOCK:
            if getattr(state, "engine", None) is None:
                engine = make_engine()
                create_db(engine)
                state.engine = engine
    return state.engine


def get_session(engine: Engine = Depends(get_engine)) -> Iterator[Session]:
    """One session per request. Handlers commit explicitly; an error means nothing is saved."""
    with Session(engine) as session:
        yield session


def get_trust_model(request: Request, cfg: dict[str, Any] = Depends(get_config)) -> TrustModel:
    state = request.app.state
    if getattr(state, "trust_model", None) is None:
        path = REPO_ROOT / cfg["paths"]["models_dir"] / f"{cfg['trust_model']['version']}.joblib"
        if not path.exists():
            raise ModelUnavailable(f"trust model not found at {path.name}: run `make train`")
        with _LOCK:
            state.trust_model = TrustModel.load(path)
    return state.trust_model


def get_classifier(request: Request) -> DisputeClassifier:
    classifier = getattr(request.app.state, "classifier", None)
    return classifier if classifier is not None else load_classifier()


def require_admin_if_protected(
    request: Request,
    session: Session = Depends(get_session),
    cfg: dict[str, Any] = Depends(get_config),
) -> None:
    """With accounts on (api.protect_admin), the analyst console needs an admin token."""
    if not cfg["api"].get("protect_admin", False):
        return
    from app.auth import bearer_token, user_from_token
    from app.enums import UserRole

    user = user_from_token(session, bearer_token(request))
    if user is None:
        raise ApiError(401, "NOT_SIGNED_IN", "please sign in")
    if user.role != UserRole.ADMIN or user.frozen:
        raise ApiError(403, "ADMIN_ONLY", "admins only")


def require_demo(
    request: Request,
    session: Session = Depends(get_session),
    cfg: dict[str, Any] = Depends(get_config),
) -> None:
    """Demo-only endpoints answer 404 when switched off in the config, and, when a demo code is
    set (SAFEORDER_DEMO_CODE), 403 unless the request carries it in the X-Demo-Code header."""
    if not cfg["api"]["demo_endpoints_enabled"]:
        raise ApiError(404, "NOT_FOUND", "not found")
    if cfg["api"].get("protect_admin", False):
        require_admin_if_protected(request, session, cfg)  # admins only, no shared demo code
        return
    expected = getattr(request.app.state, "demo_code", None)
    if expected and not hmac.compare_digest(request.headers.get("x-demo-code", ""), expected):
        raise ApiError(403, "DEMO_CODE_REQUIRED", "the demo code is missing or wrong")


def get_optional_trust_model(
    request: Request, cfg: dict[str, Any] = Depends(get_config)
) -> TrustModel | None:
    """The trust model, or None when it is not trained. Used where a money decision must not
    fail only because a score cannot be refreshed."""
    try:
        return get_trust_model(request, cfg)
    except ModelUnavailable:
        return None
