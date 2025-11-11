from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from alembic import command
from alembic.config import Config
from sqlmodel import Session, create_engine

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
    command.upgrade(get_alembic_config(), "head")


@contextmanager
def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
