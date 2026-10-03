from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import Engine

from app.api.deps import get_config, get_engine, get_trust_model, require_demo
from app.api.errors import ApiError
from app.clock import clock, to_iso
from app.demo_scenarios import DemoSetupError, load_demo_scenarios
from app.disputes.classifier import DisputeClassifier
from app.schemas import DemoResetOut, DemoResetRequest
from app.seed import SCENARIO_SETS, reset_and_load

router = APIRouter(prefix="/demo", tags=["demo"], dependencies=[Depends(require_demo)])


@router.post("/reset", response_model=DemoResetOut)
def reset(
    body: DemoResetRequest,
    request: Request,
    engine: Engine = Depends(get_engine),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    """Demo only: wipe the database and the simulated clock, then load a scenario set.

    The ``demo`` set also creates the seven demo scenarios (BLUEPRINT.md Section 12.2).
    """
    if cfg["api"].get("persist", False):
        # a persistent database holds real accounts: it is never wiped from the website
        raise ApiError(404, "NOT_FOUND", "not found")
    if body.scenario_set not in SCENARIO_SETS:
        raise ApiError(422, "VALIDATION_ERROR", f"scenario_set must be one of {SCENARIO_SETS}")
    loaded = reset_and_load(engine, body.scenario_set, cfg)
    scenarios: list[dict[str, Any]] = []
    if body.scenario_set == "demo":
        classifier: DisputeClassifier | None = getattr(request.app.state, "classifier", None)
        try:
            scenarios = load_demo_scenarios(engine, get_trust_model(request, cfg), classifier, cfg)
        except DemoSetupError as error:
            raise ApiError(
                409, "ILLEGAL_STATE", f"demo scenarios could not be set up: {error}"
            ) from error
    return {
        "scenario_set": body.scenario_set,
        "loaded": loaded,
        "now": to_iso(clock.now()),
        "scenarios": scenarios,
    }
