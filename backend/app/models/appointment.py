from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field

from app.models.base import TimestampMixin


class Appointment(TimestampMixin, table=True):
    __tablename__ = "appointments"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id")
    provider_id: int = Field(index=True)
    location: Optional[str] = Field(default=None, max_length=255)
    service_type: Optional[str] = Field(default=None, max_length=100)
    start_time: datetime
    end_time: datetime
    status: str = Field(default="scheduled", max_length=32, index=True)
    notes: Optional[str] = Field(default=None, max_length=255)
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    cancelled_reason: Optional[str] = Field(default=None, max_length=255)
    cancelled_at: Optional[datetime] = Field(default=None)


class AppointmentStatusHistory(TimestampMixin, table=True):
    __tablename__ = "appointment_status_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    appointment_id: int = Field(foreign_key="appointments.id")
    status: str = Field(max_length=32)
    changed_by: Optional[int] = Field(default=None, foreign_key="users.id")
    changed_at: datetime = Field(default_factory=datetime.utcnow)
    note: Optional[str] = Field(default=None, max_length=255)
