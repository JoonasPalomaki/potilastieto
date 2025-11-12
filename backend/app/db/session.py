from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:  # pragma: no cover - typing only
    from alembic.config import Config
    from alembic.script import ScriptDirectory

from sqlmodel import SQLModel, Session, create_engine

from app.core.config import settings

ALEMBIC_INSTALL_HINT = 'Alembic is required to run database migrations. Install it with `pip install -e ".[dev]"`.'


def _require_alembic() -> tuple[Any, Any, Any]:
    try:
        from alembic import command as alembic_command
        from alembic.config import Config as AlembicConfig
        from alembic.script import ScriptDirectory as AlembicScriptDirectory
    except ImportError as exc:  # pragma: no cover - exercised via unit test
        raise RuntimeError(ALEMBIC_INSTALL_HINT) from exc

    return alembic_command, AlembicConfig, AlembicScriptDirectory

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def get_alembic_config() -> "Config":
    _, AlembicConfig, _ = _require_alembic()
    migrations_path = Path(__file__).resolve().parent / "migrations"
    config = AlembicConfig()
    config.set_main_option("script_location", str(migrations_path))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def init_db() -> None:
    alembic_command, _, AlembicScriptDirectory = _require_alembic()
    config = get_alembic_config()
    alembic_command.upgrade(config, "head")
    SQLModel.metadata.create_all(engine)
    script = AlembicScriptDirectory.from_config(config)
    head_revision = script.get_current_head()
    if head_revision:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"
            )
            connection.exec_driver_sql("DELETE FROM alembic_version")
            connection.exec_driver_sql(
                "INSERT INTO alembic_version (version_num) VALUES (?)",
                (head_revision,),
            )


@contextmanager
def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
