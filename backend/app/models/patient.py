from __future__ import annotations


from datetime import date, datetime
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field

from app.models.base import TimestampMixin


class Patient(TimestampMixin, table=True):
    __tablename__ = "patients"

    id: Optional[int] = Field(default=None, primary_key=True)
    identifier: Optional[str] = Field(default=None, unique=True, index=True, max_length=64)
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    date_of_birth: Optional[date] = Field(default=None)
    sex: Optional[str] = Field(default=None, max_length=20)
    language: Optional[str] = Field(default=None, max_length=32)
    contact_info: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
    )
    status: str = Field(default="active", max_length=32)
    archived_at: Optional[datetime] = Field(default=None)
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")


class PatientContact(TimestampMixin, table=True):
    __tablename__ = "patient_contacts"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id")
    name: str = Field(max_length=150)
    relationship: Optional[str] = Field(default=None, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=100)
    is_guardian: bool = Field(default=False)


class Consent(TimestampMixin, table=True):
    __tablename__ = "consents"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id")
    type: str = Field(max_length=100)
    status: str = Field(max_length=50)
    granted_at: Optional[datetime] = Field(default=None)
    revoked_at: Optional[datetime] = Field(default=None)
    notes: Optional[str] = Field(default=None, max_length=255)


class PatientHistory(TimestampMixin, table=True):
    __tablename__ = "patient_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id")
    changed_by: Optional[int] = Field(default=None, foreign_key="users.id")
    change_type: str = Field(max_length=50)
    snapshot: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
    )
    reason: Optional[str] = Field(default=None, max_length=255)
    changed_at: datetime = Field(default_factory=datetime.utcnow)
