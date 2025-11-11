from __future__ import annotations


import re
from datetime import date, datetime
from typing import ClassVar, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError, model_validator


_HETU_CHECK_CHARS = "0123456789ABCDEFHJKLMNPRSTUVWXY"
_HETU_PATTERN = re.compile(
    r"^(?P<date>\d{6})(?P<sep>[A+-])(?P<individual>\d{3})(?P<checksum>[0-9A-Z])$"
)


def _parse_finnish_hetu(value: str) -> Tuple[date, str]:
    hetu = value.strip().upper()
    match = _HETU_PATTERN.match(hetu)
    if not match:
        raise ValueError("Henkilötunnuksen muoto on virheellinen")

    day = int(match.group("date")[:2])
    month = int(match.group("date")[2:4])
    year_suffix = int(match.group("date")[4:])
    separator = match.group("sep")
    individual = match.group("individual")
    checksum = match.group("checksum")

    century_map = {
        "+": 1800,
        "-": 1900,
        "A": 2000,
        "B": 2100,
        "C": 2200,
        "D": 2300,
        "E": 2400,
        "F": 2500,
    }
    if separator not in century_map:
        raise ValueError("Henkilötunnuksen vuosisatamerkki on virheellinen")

    year = century_map[separator] + year_suffix
    try:
        birth_date = date(year, month, day)
    except ValueError as exc:  # pragma: no cover - defensive branch
        raise ValueError("Henkilötunnuksen syntymäaika on virheellinen") from exc

    checksum_source = f"{match.group('date')}{individual}"
    expected_checksum = _HETU_CHECK_CHARS[int(checksum_source) % 31]
    if checksum != expected_checksum:
        raise ValueError("Henkilötunnuksen tarkistusmerkki on virheellinen")

    sex = "male" if int(individual) % 2 else "female"
    return birth_date, sex


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
    _require_demographics: ClassVar[bool] = True

    identifier: Optional[str] = Field(default=None, max_length=64)
    first_name: str
    last_name: str
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    language: Optional[str] = None
    contact_info: Optional[ContactInfo] = None
    status: Optional[str] = Field(default="active")

    @model_validator(mode="after")
    def _validate_identifier_and_demographics(self) -> "PatientBase":
        identifier = self.identifier
        if isinstance(identifier, str):
            identifier = identifier.strip() or None
            if identifier:
                identifier = identifier.upper()
        self.identifier = identifier

        sex_value = self.sex
        normalized_sex: Optional[str] = None
        if isinstance(sex_value, str):
            sex_clean = sex_value.strip()
            if sex_clean:
                normalized_sex = sex_clean.lower()
        self.sex = normalized_sex

        errors: List[dict[str, object]] = []

        if identifier:
            try:
                hetu_birth_date, hetu_sex = _parse_finnish_hetu(identifier)
            except ValueError as exc:
                errors.append(
                    {
                        "type": "value_error",
                        "loc": ("identifier",),
                        "msg": str(exc),
                        "input": identifier,
                        "ctx": {"error": str(exc)},
                    }
                )
            else:
                if self.date_of_birth and self.date_of_birth != hetu_birth_date:
                    errors.append(
                        {
                            "type": "value_error",
                            "loc": ("date_of_birth",),
                            "msg": "syntymäaika ei täsmää henkilötunnuksen kanssa",
                            "input": self.date_of_birth,
                            "ctx": {"error": "syntymäaika ei täsmää henkilötunnuksen kanssa"},
                        }
                    )
                if normalized_sex and normalized_sex != hetu_sex:
                    errors.append(
                        {
                            "type": "value_error",
                            "loc": ("sex",),
                            "msg": "sukupuoli ei täsmää henkilötunnuksen kanssa",
                            "input": sex_value,
                            "ctx": {"error": "sukupuoli ei täsmää henkilötunnuksen kanssa"},
                        }
                    )
        else:
            require_pair = getattr(type(self), "_require_demographics", True)
            if require_pair:
                if not self.date_of_birth:
                    errors.append(
                        {
                            "type": "missing",
                            "loc": ("date_of_birth",),
                            "msg": "syntymäaika on pakollinen ilman henkilötunnusta",
                            "input": self.date_of_birth,
                            "ctx": {"error": "syntymäaika on pakollinen ilman henkilötunnusta"},
                        }
                    )
                if not normalized_sex:
                    errors.append(
                        {
                            "type": "missing",
                            "loc": ("sex",),
                            "msg": "sukupuoli on pakollinen ilman henkilötunnusta",
                            "input": sex_value,
                            "ctx": {"error": "sukupuoli on pakollinen ilman henkilötunnusta"},
                        }
                    )

        if errors:
            raise ValidationError.from_exception_data(type(self).__name__, errors)
        return self


class PatientCreate(PatientBase):
    consents: List[ConsentCreate] = Field(default_factory=list)
    contacts: List[PatientContactCreate] = Field(default_factory=list)


class PatientUpdate(PatientBase):
    _require_demographics: ClassVar[bool] = False

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


class PatientMergeRequest(BaseModel):
    source_patient_id: int


class PatientArchiveRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=255)

    @model_validator(mode="after")
    def _normalize_reason(self) -> "PatientArchiveRequest":
        normalized = self.reason.strip()
        if not normalized:
            raise ValidationError.from_exception_data(
                type(self).__name__,
                [
                    {
                        "type": "missing",
                        "loc": ("reason",),
                        "msg": "perustelu on pakollinen",
                        "input": self.reason,
                    }
                ],
            )
        self.reason = normalized
        return self


class PatientRestoreRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=255)

    @model_validator(mode="after")
    def _normalize_reason(self) -> "PatientRestoreRequest":
        normalized = self.reason.strip()
        if not normalized:
            raise ValidationError.from_exception_data(
                type(self).__name__,
                [
                    {
                        "type": "missing",
                        "loc": ("reason",),
                        "msg": "perustelu on pakollinen",
                        "input": self.reason,
                    }
                ],
            )
        self.reason = normalized
        return self
