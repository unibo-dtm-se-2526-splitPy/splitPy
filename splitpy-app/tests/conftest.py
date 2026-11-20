"""Fixtures shared by the tests that need a database."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from splitpy_app.adapters.persistence.models import Base


@pytest.fixture
def sessions(tmp_path):
    """A file database with the schema of the models, enforcing foreign keys as Postgres does."""
    engine = create_engine(f"sqlite:///{tmp_path / 'splitpy.db'}")
    event.listen(
        engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys = ON")
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(engine)
    engine.dispose()
