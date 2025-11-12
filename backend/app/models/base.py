from __future__ import annotations


from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import declared_attr
from sqlmodel import Field, SQLModel


def _timestamp_field() -> Field:
    return Field(
        default=None,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "nullable": False,
            "server_default": func.now(),
            "onupdate": func.now(),
        },
    )


class TimestampMixin(SQLModel):
    created_at: datetime
    updated_at: datetime

    @declared_attr
    def created_at(cls):  # type: ignore[override]
        return _timestamp_field()

    @declared_attr
    def updated_at(cls):  # type: ignore[override]
        return _timestamp_field()
