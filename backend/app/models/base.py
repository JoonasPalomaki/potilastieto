from __future__ import annotations


from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class TimestampMixin(SQLModel):
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
        ),
    )
