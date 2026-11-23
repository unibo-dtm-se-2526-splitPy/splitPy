"""Databases for the tests: SQLite on a file, and a real Postgres in a throwaway container."""

from collections.abc import Callable, Iterator
from itertools import count

import pytest
from sqlalchemy import Engine, create_engine, event, make_url, text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.community.postgres import PostgresContainer

from splitpy_app.adapters.persistence.models import Base

BACKENDS = ["sqlite", "postgres"]

_database_names = (f"splitpy_{n}" for n in count())


@pytest.fixture(scope="session")
def postgres_server() -> Iterator[str]:
    """One container for the whole run: each test gets a database of its own inside it."""
    with PostgresContainer("postgres:17-alpine", driver="psycopg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture
def postgres_url(postgres_server: str) -> Iterator[str]:
    name = next(_database_names)
    admin = create_engine(postgres_server, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f"CREATE DATABASE {name}"))
    yield make_url(postgres_server).set(database=name).render_as_string(hide_password=False)
    with admin.connect() as connection:
        connection.execute(text(f"DROP DATABASE {name} WITH (FORCE)"))
    admin.dispose()


@pytest.fixture
def sqlite_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'splitpy.db'}"


@pytest.fixture(params=BACKENDS)
def database_url(request) -> str:
    return request.getfixturevalue(f"{request.param}_url")


@pytest.fixture
def database(request) -> Iterator[Callable[[str], sessionmaker[Session]]]:
    """Opens the schema of the models on a backend, with foreign keys enforced on both."""
    engines: list[Engine] = []

    def open_backend(backend: str) -> sessionmaker[Session]:
        engine = create_engine(request.getfixturevalue(f"{backend}_url"))
        if engine.dialect.name == "sqlite":
            event.listen(
                engine,
                "connect",
                lambda connection, _: connection.execute("PRAGMA foreign_keys = ON"),
            )
        Base.metadata.create_all(engine)
        engines.append(engine)
        return sessionmaker(engine)

    yield open_backend
    for engine in engines:
        engine.dispose()


@pytest.fixture(params=BACKENDS)
def sessions(request, database) -> sessionmaker[Session]:
    return database(request.param)
