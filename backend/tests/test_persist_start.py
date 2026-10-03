"""Starting on a persistent database: synthetic data first, then the admin, nothing wiped."""

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import seed
from app.clock import clock
from app.db import create_db, make_engine
from app.main import create_app
from app.models import Buyer, Seller, User
from app.seed import seed_minimal


def test_admin_is_created_after_the_synthetic_data_and_users_survive_a_restart(
    tmp_path, monkeypatch
) -> None:
    clock.reset()
    engine = make_engine(f"sqlite:///{tmp_path / 'persist.db'}")
    create_db(engine)

    def fake_load(eng, cfg=None):  # the synthetic data owns the first ids
        with Session(eng) as session:
            seed_minimal(session)
        return {"sellers": 2, "buyers": 2}

    monkeypatch.setattr(seed, "load_from_files", fake_load)
    monkeypatch.setattr("app.demo_scenarios.load_demo_scenarios", lambda *a, **k: [])
    monkeypatch.setenv("SAFEORDER_PERSIST", "1")
    monkeypatch.setenv("SAFEORDER_ADMIN_PHONE", "01900000000")
    monkeypatch.setenv("SAFEORDER_ADMIN_PIN", "11111")

    def boot() -> TestClient:
        app = create_app(engine=engine, serve_frontend=False)
        return TestClient(app)

    with boot() as client:  # the lifespan runs the persistent start
        admin = {"phone": "01900000000", "pin": "11111"}
        assert client.post("/api/auth/login", json=admin).status_code == 200
        buyer = {"name": "Karim Buyer", "phone": "01711111111", "pin": "12345"}
        assert client.post("/api/auth/register", json=buyer).status_code == 201

    with Session(engine) as session:
        buyers = {b.id for b in session.exec(select(Buyer)).all()}
        # the synthetic ids first, then the admin and the buyer continue after them
        assert buyers == {"B-0001", "B-0002", "B-000003", "B-000004"}
        assert len(session.exec(select(Seller)).all()) == 2
        assert len(session.exec(select(User)).all()) == 2

    with boot() as client:  # a second start must not wipe or duplicate anything
        again = {"phone": "01711111111", "pin": "12345"}
        assert client.post("/api/auth/login", json=again).status_code == 200
    with Session(engine) as session:
        assert len(session.exec(select(User)).all()) == 2
        assert len(session.exec(select(Seller)).all()) == 2
    clock.reset()


def test_demo_reset_is_off_on_a_persistent_database(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SAFEORDER_PERSIST", "1")
    engine = make_engine(f"sqlite:///{tmp_path / 'p2.db'}")
    create_db(engine)
    from app.config import load_config
    from app.deploy import apply_env

    app = create_app(engine=engine, cfg=apply_env(load_config()), serve_frontend=False)
    client = TestClient(app)
    response = client.post("/api/demo/reset", json={"scenario_set": "empty"})
    assert response.status_code == 404
