from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AppointmentStatusRead(BaseModel):
    status: str
    changed_at: datetime
    changed_by: Optional[int]
    note: Optional[str] = None


class AppointmentBase(BaseModel):
    patient_id: int
    provider_id: int
    service_type: Optional[str] = None
    location: Optional[str] = None
    start_time: datetime
    end_time: datetime
    notes: Optional[str] = None


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(BaseModel):
    service_type: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    cancelled_reason: Optional[str] = None
    notify_patient: Optional[bool] = None


class AppointmentRead(AppointmentBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime
    cancelled_reason: Optional[str]
    cancelled_at: Optional[datetime]
    status_history: List[AppointmentStatusRead] = Field(default_factory=list)


class AppointmentSummary(BaseModel):
    id: int
    patient_id: int
    provider_id: int
    service_type: Optional[str]
    start_time: datetime
    end_time: datetime
    status: str


class AppointmentCancelRequest(BaseModel):
    reason: Optional[str] = None
    notify_patient: bool = False


class AppointmentRescheduleRequest(BaseModel):
    start_time: datetime
    end_time: datetime
    reason: Optional[str] = None


class AvailabilitySlot(BaseModel):
    start_time: datetime
    end_time: datetime


class AppointmentAvailability(BaseModel):
    provider_id: int
    location: Optional[str] = None
    slots: List[AvailabilitySlot] = Field(default_factory=list)
