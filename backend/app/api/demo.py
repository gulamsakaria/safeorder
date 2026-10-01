from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import Engine

from app.api.deps import get_config, get_engine, require_demo
from app.api.errors import ApiError
from app.clock import clock, to_iso
from app.schemas import DemoResetOut, DemoResetRequest
from app.seed import SCENARIO_SETS, reset_and_load

router = APIRouter(prefix="/demo", tags=["demo"], dependencies=[Depends(require_demo)])


@router.post("/reset", response_model=DemoResetOut)
def reset(
    body: DemoResetRequest,
    engine: Engine = Depends(get_engine),
    cfg: dict[str, Any] = Depends(get_config),
) -> dict[str, Any]:
    """Demo only: wipe the database and the simulated clock, then load a scenario set."""
    if body.scenario_set not in SCENARIO_SETS:
        raise ApiError(422, "VALIDATION_ERROR", f"scenario_set must be one of {SCENARIO_SETS}")
    loaded = reset_and_load(engine, body.scenario_set, cfg)
    return {"scenario_set": body.scenario_set, "loaded": loaded, "now": to_iso(clock.now())}
