from __future__ import annotations


from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import declarative_mixin
from sqlmodel import Field


@declarative_mixin
class TimestampMixin:
    """Reusable created/updated timestamp columns for SQLModel tables."""

    created_at: datetime = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "nullable": False,
            "server_default": func.now(),
        },
    )
    updated_at: datetime = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "nullable": False,
            "server_default": func.now(),
            "onupdate": func.now(),
        },
    )
