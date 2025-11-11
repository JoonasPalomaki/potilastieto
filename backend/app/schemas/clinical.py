from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class VisitBase(BaseModel):
    patient_id: int
    appointment_id: Optional[int] = None
    visit_type: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = Field(default="planned")
    location: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    attending_provider_id: Optional[int] = None


class VisitCreate(VisitBase):
    pass


class VisitUpdate(BaseModel):
    visit_type: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    attending_provider_id: Optional[int] = None


class VisitRead(VisitBase):
    id: int
    created_at: datetime
    updated_at: datetime


class ClinicalNoteBase(BaseModel):
    visit_id: int
    patient_id: int
    author_id: Optional[int] = None
    note_type: Optional[str] = None
    title: Optional[str] = None
    content: str


class ClinicalNoteCreate(ClinicalNoteBase):
    pass


class ClinicalNoteUpdate(BaseModel):
    note_type: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None


class ClinicalNoteRead(ClinicalNoteBase):
    id: int
    created_at: datetime
    updated_at: datetime


class OrderBase(BaseModel):
    visit_id: int
    patient_id: int
    ordered_by_id: Optional[int] = None
    order_type: str
    status: Optional[str] = Field(default="draft")
    details: dict = Field(default_factory=dict)
    placed_at: Optional[datetime] = None


class OrderCreate(OrderBase):
    pass


class OrderUpdate(BaseModel):
    order_type: Optional[str] = None
    status: Optional[str] = None
    details: Optional[dict] = None
    placed_at: Optional[datetime] = None
    ordered_by_id: Optional[int] = None


class OrderRead(OrderBase):
    id: int
    created_at: datetime
    updated_at: datetime


class LabResultBase(BaseModel):
    order_id: int
    result_type: str
    status: Optional[str] = Field(default="pending")
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    observed_at: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)


class LabResultCreate(LabResultBase):
    pass


class LabResultUpdate(BaseModel):
    status: Optional[str] = None
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    observed_at: Optional[datetime] = None
    metadata: Optional[dict] = None


class LabResultRead(LabResultBase):
    id: int
    created_at: datetime
    updated_at: datetime


class InvoiceBase(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    total_amount: Decimal
    currency: Optional[str] = Field(default="EUR")
    status: Optional[str] = Field(default="draft")
    issued_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceUpdate(BaseModel):
    total_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    issued_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    metadata: Optional[dict] = None


class InvoiceRead(InvoiceBase):
    id: int
    created_at: datetime
    updated_at: datetime
