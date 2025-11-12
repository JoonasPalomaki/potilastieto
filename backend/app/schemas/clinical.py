from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


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
    model_config = ConfigDict(populate_by_name=True)

    order_id: int
    result_type: str
    status: Optional[str] = Field(default="pending")
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    observed_at: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict, alias="metadata_json")


class LabResultCreate(LabResultBase):
    pass


class LabResultUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Optional[str] = None
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    observed_at: Optional[datetime] = None
    metadata: Optional[dict] = Field(default=None, alias="metadata_json")


class LabResultRead(LabResultBase):
    id: int
    created_at: datetime
    updated_at: datetime


class InvoiceBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    patient_id: int
    visit_id: Optional[int] = None
    total_amount: Decimal
    currency: Optional[str] = Field(default="EUR")
    status: Optional[str] = Field(default="draft")
    issued_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict, alias="metadata_json")


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    issued_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    metadata: Optional[dict] = Field(default=None, alias="metadata_json")


class InvoiceRead(InvoiceBase):
    id: int
    created_at: datetime
    updated_at: datetime


class VisitBasicsPanelBase(BaseModel):
    visit_type: Optional[str] = None
    location: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    attending_provider_id: Optional[int] = None


class VisitBasicsPanelRead(VisitBasicsPanelBase):
    updated_at: Optional[datetime] = None


class VisitReasonPanelRead(BaseModel):
    reason: Optional[str] = None
    updated_at: Optional[datetime] = None


class VisitReasonPanelUpdate(BaseModel):
    reason: str = Field(..., min_length=1, max_length=255)


class VisitNarrativePanelRead(BaseModel):
    content: Optional[str] = None
    author_id: Optional[int] = None
    updated_at: Optional[datetime] = None


class VisitNarrativePanelUpdate(BaseModel):
    content: str = Field(..., min_length=1)


class VisitDiagnosisEntry(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    description: Optional[str] = None
    is_primary: bool = Field(default=False)


class VisitDiagnosesPanelRead(BaseModel):
    diagnoses: List[VisitDiagnosisEntry] = Field(default_factory=list)
    author_id: Optional[int] = None
    updated_at: Optional[datetime] = None


class VisitDiagnosesPanelUpdate(BaseModel):
    diagnoses: List[VisitDiagnosisEntry] = Field(..., min_length=1)


class VisitOrderItem(BaseModel):
    order_type: str = Field(..., min_length=1, max_length=100)
    status: Optional[str] = Field(default=None, max_length=32)
    details: dict = Field(default_factory=dict)
    placed_at: Optional[datetime] = None
    ordered_by_id: Optional[int] = None


class VisitOrdersPanelRead(BaseModel):
    orders: List[OrderRead] = Field(default_factory=list)


class VisitOrdersPanelUpdate(BaseModel):
    orders: List[VisitOrderItem] = Field(..., min_length=1)


class VisitSummaryPanelRead(VisitNarrativePanelRead):
    pass


class InitialVisitRead(BaseModel):
    id: int
    patient_id: int
    appointment_id: Optional[int] = None
    basics: VisitBasicsPanelRead
    reason: VisitReasonPanelRead
    anamnesis: VisitNarrativePanelRead
    status: VisitNarrativePanelRead
    diagnoses: VisitDiagnosesPanelRead
    orders: VisitOrdersPanelRead
    summary: VisitSummaryPanelRead
    created_at: datetime
    updated_at: datetime


class InitialVisitCreate(BaseModel):
    appointment_id: int
    basics: Optional[VisitBasicsPanelBase] = None
    reason: Optional[VisitReasonPanelUpdate] = None
    anamnesis: Optional[VisitNarrativePanelUpdate] = None
    status: Optional[VisitNarrativePanelUpdate] = None
    diagnoses: Optional[VisitDiagnosesPanelUpdate] = None
    orders: Optional[VisitOrdersPanelUpdate] = None
    summary: Optional[VisitNarrativePanelUpdate] = None


class VisitBasicsPanelUpdate(VisitBasicsPanelBase):
    pass
