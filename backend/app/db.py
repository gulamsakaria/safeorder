"""Database engine, create/reset and small helpers."""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sqlalchemy import Engine, event, text
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401  (registers the tables)
from app.clock import clock
from app.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[2]

_APPEND_ONLY_TRIGGERS = (
    """CREATE TRIGGER IF NOT EXISTS audit_log_no_update BEFORE UPDATE ON audit_log
       BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END""",
    """CREATE TRIGGER IF NOT EXISTS audit_log_no_delete BEFORE DELETE ON audit_log
       BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END""",
)


def make_engine(url: str | None = None) -> Engine:
    if url is None:
        db_path = REPO_ROOT / load_config()["paths"]["database"]
        db_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record) -> None:  # noqa: ANN001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def create_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        for statement in _APPEND_ONLY_TRIGGERS:
            conn.execute(text(statement))


def reset_db(engine: Engine) -> None:
    """Drop everything, recreate empty tables and rewind the simulated clock."""
    SQLModel.metadata.drop_all(engine)
    create_db(engine)
    clock.reset()


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def next_id(session: Session, model: type[SQLModel], prefix: str, width: int = 4) -> str:
    """Next readable id such as O-0001 (largest existing numeric suffix plus one)."""
    ids = session.exec(select(model.id)).all()  # type: ignore[attr-defined]
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    numbers = [int(m.group(1)) for i in ids if (m := pattern.match(str(i)))]
    return f"{prefix}-{(max(numbers, default=0) + 1):0{width}d}"


def write_audit(
    session: Session,
    actor: str,
    action: str,
    entity: str,
    entity_id: str,
    payload_json: str = "{}",
    created_at: datetime | None = None,
) -> None:
    session.add(
        models.AuditLog(
            actor=actor,
            action=action,
            entity=entity,
            entity_id=entity_id,
            payload_json=payload_json,
            created_at=created_at or clock.now(),
        )
    )
