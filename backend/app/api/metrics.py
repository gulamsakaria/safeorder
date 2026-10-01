import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import REPO_ROOT, get_config
from app.schemas import MetricsOut

router = APIRouter(tags=["metrics"])
SUMMARY_FILE = "summary.json"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/metrics/summary", response_model=MetricsOut)
def metrics_summary(cfg: dict[str, Any] = Depends(get_config)) -> dict[str, Any]:
    """Evaluation numbers exactly as the evaluation scripts wrote them.

    ``summary`` is reports/summary.json (Step 12); until it exists the individual reports are
    still returned under ``reports``. Nothing is computed here, so a missing number stays missing.
    """
    directory = REPO_ROOT / cfg["paths"]["reports_dir"]
    summary_path = directory / SUMMARY_FILE
    reports = {p.stem: _read(p) for p in sorted(directory.glob("*.json")) if p.name != SUMMARY_FILE}
    summary = _read(summary_path) if summary_path.exists() else None
    return {"available": summary is not None, "summary": summary, "reports": reports}
