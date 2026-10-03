"""A downloaded copy of the repository must open in the browser without building anything."""

import copy
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import load_config
from app.deploy import apply_env
from app.main import create_app

REPO = Path(__file__).resolve().parents[2]


def test_site_folder_is_served_when_there_is_no_build_output() -> None:
    cfg = copy.deepcopy(apply_env(load_config()))
    cfg["web"]["dist_dir"] = "frontend/does-not-exist"
    client = TestClient(create_app(cfg=cfg, serve_frontend=True))
    page = client.get("/")
    assert page.status_code == 200
    assert '<div id="root">' in page.text
    assert client.get("/config.js").status_code == 200
    assert client.get("/api/nothing-here").status_code == 404  # the API is not shadowed


def test_launcher_files_exist_and_the_batch_file_has_windows_line_endings() -> None:
    assert (REPO / "run_local.py").is_file()
    assert (REPO / "run_local.sh").read_bytes().startswith(b"#!/bin/sh\n")
    assert b"run_local.py" in (REPO / "run_local.bat").read_bytes()


def test_readme_tells_judges_how_to_run_it() -> None:
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "python run_local.py" in readme
    assert "docker run" in readme
