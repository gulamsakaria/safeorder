"""Write the API description to docs/openapi.json (BLUEPRINT.md Step 8).

Usage: PYTHONPATH=backend:. python -m scripts.export_openapi
"""

import json
from pathlib import Path

from app.main import app

TARGET = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    TARGET.write_text(render(), encoding="utf-8")
    print(f"wrote {TARGET.relative_to(TARGET.parents[1])}")


if __name__ == "__main__":
    main()
