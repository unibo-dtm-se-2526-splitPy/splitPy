"""Migrations build the schema of the models, so no database ever needs create_all."""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, create_engine, inspect

from splitpy_app.adapters.persistence.models import Base

ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"


def alembic_config(url: str | None = None) -> Config:
    config = Config(ALEMBIC_INI)
    if url is not None:
        config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def database_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'splitpy.db'}"


@pytest.fixture
def engine(database_url):
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


class TestMigrations:
    def test_history_has_a_single_head(self):
        assert len(ScriptDirectory.from_config(alembic_config()).get_heads()) == 1

    def test_upgrade_builds_the_schema_of_the_models(self, database_url, engine):
        command.upgrade(alembic_config(database_url), "head")
        with engine.connect() as connection:
            differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert differences == []

    def test_upgrade_creates_the_named_check_constraints(self, database_url, engine):
        command.upgrade(alembic_config(database_url), "head")
        inspector = inspect(engine)
        for table in Base.metadata.sorted_tables:
            expected = {
                constraint.name
                for constraint in table.constraints
                if isinstance(constraint, CheckConstraint)
            }
            created = {check["name"] for check in inspector.get_check_constraints(table.name)}
            assert created == expected, table.name

    def test_downgrade_removes_every_table(self, database_url, engine):
        config = alembic_config(database_url)
        command.upgrade(config, "head")
        command.downgrade(config, "base")
        assert inspect(engine).get_table_names() == ["alembic_version"]

    def test_database_url_comes_from_the_environment(self, monkeypatch, database_url, engine):
        monkeypatch.setenv("DATABASE_URL", database_url)
        command.upgrade(alembic_config(), "head")
        assert "groups" in inspect(engine).get_table_names()
