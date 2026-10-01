from fastapi.testclient import TestClient

from app.config import load_config
from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_config_has_blueprint_thresholds() -> None:
    rules = load_config()["rules"]
    assert rules["hold_period_hours"] == 72
    assert rules["seller_response_deadline_hours"] == 48
    assert rules["trust"]["trusted_min"] == 70
    assert rules["routing"]["high_amount_bdt"] == 5000
