from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, JSON, Numeric, Text
from sqlmodel import Field

from app.models.base import TimestampMixin


class Visit(TimestampMixin, table=True):
    __tablename__ = "visits"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id", index=True)
    appointment_id: Optional[int] = Field(default=None, foreign_key="appointments.id", index=True)
    visit_type: Optional[str] = Field(default=None, max_length=100)
    reason: Optional[str] = Field(default=None, max_length=255)
    status: str = Field(default="planned", max_length=32, index=True)
    location: Optional[str] = Field(default=None, max_length=255)
    started_at: Optional[datetime] = Field(default=None)
    ended_at: Optional[datetime] = Field(default=None)
    attending_provider_id: Optional[int] = Field(default=None, foreign_key="users.id")


class ClinicalNote(TimestampMixin, table=True):
    __tablename__ = "clinical_notes"

    id: Optional[int] = Field(default=None, primary_key=True)
    visit_id: int = Field(foreign_key="visits.id", index=True)
    patient_id: int = Field(foreign_key="patients.id", index=True)
    author_id: Optional[int] = Field(default=None, foreign_key="users.id")
    note_type: Optional[str] = Field(default=None, max_length=100)
    title: Optional[str] = Field(default=None, max_length=255)
    content: str = Field(sa_column=Column(Text, nullable=False))


class Order(TimestampMixin, table=True):
    __tablename__ = "orders"

    id: Optional[int] = Field(default=None, primary_key=True)
    visit_id: int = Field(foreign_key="visits.id", index=True)
    patient_id: int = Field(foreign_key="patients.id", index=True)
    ordered_by_id: Optional[int] = Field(default=None, foreign_key="users.id")
    order_type: str = Field(max_length=100)
    status: str = Field(default="draft", max_length=32, index=True)
    details: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
    )
    placed_at: Optional[datetime] = Field(default=None)


class LabResult(TimestampMixin, table=True):
    __tablename__ = "lab_results"

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    result_type: str = Field(max_length=100)
    status: str = Field(default="pending", max_length=32, index=True)
    value: Optional[str] = Field(default=None, max_length=255)
    unit: Optional[str] = Field(default=None, max_length=32)
    reference_range: Optional[str] = Field(default=None, max_length=255)
    observed_at: Optional[datetime] = Field(default=None)
    metadata: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
    )


class Invoice(TimestampMixin, table=True):
    __tablename__ = "invoices"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id", index=True)
    visit_id: Optional[int] = Field(default=None, foreign_key="visits.id", index=True)
    total_amount: Decimal = Field(
        sa_column=Column(Numeric(precision=12, scale=2), nullable=False)
    )
    currency: str = Field(default="EUR", max_length=8)
    status: str = Field(default="draft", max_length=32, index=True)
    issued_at: Optional[datetime] = Field(default=None)
    due_at: Optional[datetime] = Field(default=None)
    metadata: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
    )
