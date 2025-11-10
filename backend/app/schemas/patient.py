from __future__ import annotations


from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Address(BaseModel):
    street: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None


class ContactInfo(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[Address] = None


class ConsentBase(BaseModel):
    type: str
    status: str
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    notes: Optional[str] = None


class ConsentCreate(ConsentBase):
    pass


class ConsentRead(ConsentBase):
    id: int


class PatientContactBase(BaseModel):
    name: str
    relationship: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_guardian: bool = False


class PatientContactCreate(PatientContactBase):
    pass


class PatientContactRead(PatientContactBase):
    id: int


class PatientHistoryRead(BaseModel):
    id: int
    changed_at: datetime
    changed_by: Optional[int]
    change_type: str
    reason: Optional[str]


class PatientBase(BaseModel):
    identifier: Optional[str] = Field(default=None, max_length=64)
    first_name: str
    last_name: str
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    language: Optional[str] = None
    contact_info: Optional[ContactInfo] = None
    status: Optional[str] = Field(default="active")


class PatientCreate(PatientBase):
    consents: List[ConsentCreate] = Field(default_factory=list)
    contacts: List[PatientContactCreate] = Field(default_factory=list)


class PatientUpdate(PatientBase):
    consents: Optional[List[ConsentCreate]] = None
    contacts: Optional[List[PatientContactCreate]] = None
    reason: Optional[str] = None


class PatientRead(PatientBase):
    id: int
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime]
    consents: List[ConsentRead] = Field(default_factory=list)
    contacts: List[PatientContactRead] = Field(default_factory=list)
    history: List[PatientHistoryRead] = Field(default_factory=list)


class PatientSummary(BaseModel):
    id: int
    identifier: Optional[str]
    full_name: str
    date_of_birth: Optional[date]
    status: str
    updated_at: datetime
