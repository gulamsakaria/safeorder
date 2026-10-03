"""Running the whole app as one web service: frontend serving, demo code, proxy address, seeding."""

import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import deploy
from app.config import load_config
from app.main import create_app


@pytest.fixture()
def dist(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>INDEX</html>")
    (tmp_path / "assets" / "app-abc123.js").write_text("console.log(1)")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    (tmp_path.parent / "secret.txt").write_text("outside")
    return tmp_path


def make_client(monkeypatch, dist, engine=None, **env) -> TestClient:
    monkeypatch.setenv("SAFEORDER_SERVE_FRONTEND", "1")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    cfg = copy.deepcopy(load_config())
    cfg["web"]["dist_dir"] = str(dist)
    cfg["api"]["rate_limit_per_minute"] = 0
    return TestClient(create_app(engine, None, None, cfg), raise_server_exceptions=False)


def test_the_frontend_is_served_with_a_fallback_for_client_side_routes(monkeypatch, dist) -> None:
    client = make_client(monkeypatch, dist)
    assert "INDEX" in client.get("/").text
    assert "INDEX" in client.get("/order/O-0001").text  # a route of the single-page app
    assert client.get("/favicon.svg").text == "<svg/>"
    asset = client.get("/assets/app-abc123.js")
    assert asset.status_code == 200 and "immutable" in asset.headers["cache-control"]


def test_api_and_health_still_win_over_the_frontend(monkeypatch, dist) -> None:
    client = make_client(monkeypatch, dist)
    assert client.get("/health").json() == {"status": "ok"}
    missing = client.get("/api/does/not/exist")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "NOT_FOUND"
    assert client.get("/api").status_code == 404


@pytest.mark.parametrize(
    "path", ["/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"]
)
def test_files_outside_the_build_folder_are_never_served(monkeypatch, dist, path) -> None:
    client = make_client(monkeypatch, dist)
    assert "outside" not in client.get(path).text


def test_without_the_switch_the_frontend_is_not_served(monkeypatch, dist) -> None:
    monkeypatch.delenv("SAFEORDER_SERVE_FRONTEND", raising=False)
    client = TestClient(create_app(None, None, None, copy.deepcopy(load_config())))
    assert client.get("/").status_code == 404


def test_a_missing_build_is_reported_clearly(tmp_path) -> None:
    # (create_app first falls back to the ready-built site/ folder; see test_judge_package.py)
    with pytest.raises(FileNotFoundError):
        deploy.install_frontend(FastAPI(), tmp_path / "nowhere")


def test_demo_code_protects_the_sandbox_endpoints_only(monkeypatch, dist, engine) -> None:
    client = make_client(monkeypatch, dist, engine, SAFEORDER_DEMO_CODE="open-sesame")
    body = {"hours": 1}
    denied = client.post("/api/sim/advance-clock", json=body)
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "DEMO_CODE_REQUIRED"
    assert (
        client.post("/api/sim/advance-clock", json=body, headers={"X-Demo-Code": "no"}).status_code
        == 403
    )
    ok = client.post("/api/sim/advance-clock", json=body, headers={"X-Demo-Code": "open-sesame"})
    assert ok.status_code == 200
    assert client.get("/api/sellers/search", params={"q": "x"}).status_code == 200  # not protected


def test_without_a_demo_code_the_sandbox_endpoints_stay_open(monkeypatch, dist, engine) -> None:
    monkeypatch.delenv("SAFEORDER_DEMO_CODE", raising=False)
    client = make_client(monkeypatch, dist, engine)
    assert client.post("/api/sim/advance-clock", json={"hours": 1}).status_code == 200


def test_rate_limit_counts_each_forwarded_client_separately_behind_a_proxy(
    monkeypatch, dist, engine
) -> None:
    monkeypatch.setenv("SAFEORDER_SERVE_FRONTEND", "1")
    monkeypatch.setenv("SAFEORDER_TRUST_PROXY", "1")
    cfg = deploy.apply_env(load_config())
    cfg["web"]["dist_dir"] = str(dist)
    cfg["api"]["rate_limit_per_minute"] = 2
    client = TestClient(create_app(engine, None, None, cfg), raise_server_exceptions=False)

    def hit(ip: str) -> int:
        return client.get(
            "/api/sellers/search", params={"q": "x"}, headers={"X-Forwarded-For": ip}
        ).status_code

    assert [hit("1.1.1.1") for _ in range(3)][2] == 429
    first = [hit("2.2.2.2") for _ in range(3)]
    assert first[2] == 429 and first[0] != 429  # a different visitor has their own allowance
    assert hit("3.3.3.3") != 429


def test_forwarded_header_is_ignored_unless_the_proxy_is_trusted(monkeypatch, engine) -> None:
    monkeypatch.delenv("SAFEORDER_TRUST_PROXY", raising=False)
    cfg = deploy.apply_env(load_config())
    cfg["api"]["rate_limit_per_minute"] = 2
    client = TestClient(create_app(engine, None, None, cfg), raise_server_exceptions=False)
    codes = [
        client.get(
            "/api/sellers/search", params={"q": "x"}, headers={"X-Forwarded-For": f"9.9.9.{i}"}
        ).status_code
        for i in range(3)
    ]
    assert codes[2] == 429  # spoofing the header does not buy a fresh allowance


def test_environment_overrides_do_not_change_the_shared_config(monkeypatch) -> None:
    monkeypatch.setenv("SAFEORDER_RATE_LIMIT", "7")
    monkeypatch.setenv("SAFEORDER_CORS_ORIGINS", "https://a.example, https://b.example")
    cfg = deploy.apply_env(load_config())
    assert cfg["api"]["rate_limit_per_minute"] == 7
    assert cfg["api"]["cors_origins"] == ["https://a.example", "https://b.example"]
    assert load_config()["api"]["rate_limit_per_minute"] != 7


def test_autoseed_runs_on_start_only_when_asked(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(deploy, "seed_demo", lambda app: calls.append(app))
    with TestClient(create_app(None, None, None, copy.deepcopy(load_config()))):
        pass
    assert calls == []
    monkeypatch.setenv("SAFEORDER_AUTOSEED", "1")
    with TestClient(create_app(None, None, None, copy.deepcopy(load_config()))):
        pass
    assert len(calls) == 1


def test_demo_scenarios_load_even_when_a_demo_code_and_rate_limit_are_set(
    monkeypatch, engine
) -> None:
    """The setup calls go through a private app, so the public protections cannot block them."""
    from app.demo_scenarios import load_demo_scenarios
    from app.seed import reset_and_load
    from app.trust.model import TrustModel
    from tests.test_demo import REPO

    if not (REPO / "data" / "synthetic" / "v1" / "sellers.csv").exists():
        pytest.skip("run `make data` first")
    monkeypatch.setenv("SAFEORDER_DEMO_CODE", "secret")
    cfg = copy.deepcopy(load_config())
    cfg["api"]["rate_limit_per_minute"] = 3
    reset_and_load(engine, "demo", cfg)
    model = TrustModel.load(REPO / "models" / "trust_v1.joblib")
    scenarios = load_demo_scenarios(engine, model, None, cfg)
    assert len(scenarios) == 7


def test_space_files_agree_on_the_port_and_the_sdk() -> None:
    root = deploy.REPO_ROOT
    card = (root / "deploy" / "space" / "README.md").read_text()
    dockerfile = (root / "Dockerfile").read_text()
    assert "sdk: docker" in card and "app_port: 7860" in card
    assert "${PORT:-7860}" in dockerfile and "EXPOSE 7860" in dockerfile  # Render sets PORT
    assert "SAFEORDER_AUTOSEED=1" in dockerfile and "SAFEORDER_SERVE_FRONTEND=1" in dockerfile


def test_runtime_requirements_match_what_the_model_was_trained_with() -> None:
    import json

    meta = json.loads((deploy.REPO_ROOT / "models" / "trust_v1.meta.json").read_text())
    pins = {
        line.split("==")[0].lower(): line.split("==")[1]
        for line in (deploy.REPO_ROOT / "requirements-runtime.txt").read_text().splitlines()
        if "==" in line
    }
    for library, version in meta["libraries"].items():
        assert pins[library] == version, library


def test_render_blueprint_is_a_free_docker_service_for_the_api() -> None:
    import yaml

    spec = yaml.safe_load((deploy.REPO_ROOT / "render.yaml").read_text(encoding="utf-8"))
    (service,) = spec["services"]
    assert service["type"] == "web" and service["runtime"] == "docker" and service["plan"] == "free"
    assert service["healthCheckPath"] == "/health"
    env = {e["key"]: e for e in service["envVars"]}
    assert env["SAFEORDER_PERSIST"]["value"] == "1"  # real accounts: the data must be kept
    assert env["SAFEORDER_PROTECT_ADMIN"]["value"] == "1"
    assert env["SAFEORDER_TRUST_PROXY"]["value"] == "1"
    assert env["SAFEORDER_CORS_ORIGINS"]["value"] == "https://safeorder.stratifyxglobal.com"
    for secret in ("DATABASE_URL", "SAFEORDER_ADMIN_PHONE", "SAFEORDER_ADMIN_PIN"):
        assert env[secret].get("sync") is False  # secrets: never written in the file
        assert "value" not in env[secret]


def test_the_shipped_site_has_no_backend_address_by_default() -> None:
    config = (deploy.REPO_ROOT / "site" / "config.js").read_text(encoding="utf-8")
    assert "window.SAFEORDER_API = ''" in config
