"""SQLite engine and the platform migration baseline.

The service owns this database. Health means "connected and at the expected
migration revision", not "the file exists".
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL

from ..errors import WorkbenchError

MIGRATIONS = Path(__file__).resolve().with_name("migrations")


def create_database_engine(path: Path) -> Engine:
    """Open the workspace SQLite file, creating its parent directory."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        URL.create("sqlite+pysqlite", database=str(path)),
        connect_args={"check_same_thread": False},
    )


def _config(connection: object | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def upgrade_database(engine: Engine) -> str:
    """Apply every pending migration and return the resulting revision."""

    with engine.begin() as connection:
        command.upgrade(_config(connection), "head")
    return check_database_ready(engine)


def expected_revision() -> str:
    script = ScriptDirectory.from_config(_config())
    head = script.get_current_head()
    if head is None:
        raise WorkbenchError("DATABASE_NOT_READY", "The migration baseline is missing.")
    return head


def check_database_ready(engine: Engine) -> str:
    """Verify connectivity and that the schema is at the expected revision."""

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        revision = MigrationContext.configure(connection).get_current_revision()
    expected = expected_revision()
    if revision != expected:
        raise WorkbenchError(
            "DATABASE_NOT_READY",
            "The workspace database is not at the expected migration revision.",
            expected=expected,
            current=revision,
        )
    return expected


def close_database(engine: Engine) -> None:
    engine.dispose()
