from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from app.clock import clock
from app.db import create_db, make_engine


@pytest.fixture()
def engine(tmp_path) -> Iterator[Engine]:
    clock.reset()
    eng = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    create_db(eng)
    yield eng
    clock.reset()


@pytest.fixture()
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s
