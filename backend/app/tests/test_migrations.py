from __future__ import annotations

import builtins

import pytest

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.db.session import engine, get_alembic_config, init_db


def test_alembic_head_is_applied() -> None:
    init_db()
    config = get_alembic_config()
    script = ScriptDirectory.from_config(config)
    head_revision = script.get_current_head()

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        current_revision = context.get_current_revision()

    assert current_revision == head_revision


def test_init_db_requires_alembic(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.db.session as session

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object):
        if name.startswith("alembic"):
            raise ImportError("mocked alembic missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError) as excinfo:
        session.init_db()

    message = str(excinfo.value)
    assert "Alembic is required" in message
    assert 'pip install -e ".[dev]"' in message
