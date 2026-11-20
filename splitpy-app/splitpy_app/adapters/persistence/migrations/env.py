"""Runs the migrations against the configured URL, or DATABASE_URL when none is configured."""

import os

from alembic import context
from sqlalchemy import create_engine

from splitpy_app.adapters.persistence.models import Base

url = context.config.get_main_option("sqlalchemy.url") or os.environ["DATABASE_URL"]
engine = create_engine(url)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
