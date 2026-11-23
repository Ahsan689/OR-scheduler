"""Shared test fixtures."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """An isolated in-memory SQLite session with all tables created.

    StaticPool keeps a single underlying connection so the schema created by
    ``create_all`` is visible to the session.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
