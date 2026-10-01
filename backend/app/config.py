"""Loads config/config.yaml. Every threshold lives there, not in code."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.yaml"


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    path = Path(os.environ.get("SAFEORDER_CONFIG", DEFAULT_CONFIG_PATH))
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)
