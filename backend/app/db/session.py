from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlmodel import SQLModel, Session, create_engine

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def get_alembic_config() -> Config:
    migrations_path = Path(__file__).resolve().parent / "migrations"
    config = Config()
    config.set_main_option("script_location", str(migrations_path))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def init_db() -> None:
    config = get_alembic_config()
    command.upgrade(config, "head")
    SQLModel.metadata.create_all(engine)
    script = ScriptDirectory.from_config(config)
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
