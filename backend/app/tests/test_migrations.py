from __future__ import annotations

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
