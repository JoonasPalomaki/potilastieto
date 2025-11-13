from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin


class DiagnosisCode(TimestampMixin, SQLModel, table=True):
    __tablename__ = "diagnosis_codes"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(max_length=32, unique=True, index=True)
    normalized_code: str = Field(
        max_length=32,
        unique=True,
        index=True,
        description="Normalized code without separators for lookups",
    )
    short_description: str = Field(max_length=255)
    long_description: Optional[str] = Field(default=None, max_length=2048)
    is_deleted: bool = Field(default=False, index=True)
