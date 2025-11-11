from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.models import Consent, Patient, PatientContact, PatientHistory
from app.schemas.patient import (
    ConsentCreate,
    ConsentRead,
    ContactInfo,
    PatientContactCreate,
    PatientContactRead,
    PatientCreate,
    PatientHistoryRead,
    PatientRead,
    PatientSummary,
    PatientUpdate,
)
from app.services import audit


class PatientNotFoundError(Exception):
    pass


class PatientConflictError(Exception):
    def __init__(self, code: str, *, payload: Optional[Dict[str, object]] = None) -> None:
        super().__init__(code)
        self.code = code
        self.payload = payload or {}


class PatientMergeError(Exception):
    def __init__(self, code: str, message: str, *, payload: Optional[Dict[str, object]] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.payload = payload or {}


def _to_contact_info(data: Optional[dict]) -> Optional[ContactInfo]:
    if not data:
        return None
    return ContactInfo.model_validate(data)


def _build_patient_read(session: Session, patient: Patient) -> PatientRead:
    consents = session.exec(select(Consent).where(Consent.patient_id == patient.id)).all()
    contacts = session.exec(select(PatientContact).where(PatientContact.patient_id == patient.id)).all()
    history_entries = session.exec(
        select(PatientHistory)
        .where(PatientHistory.patient_id == patient.id)
        .order_by(PatientHistory.changed_at.desc())
    ).all()
    return PatientRead(
        id=patient.id,
        identifier=patient.identifier,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
        sex=patient.sex,
        language=patient.language,
        contact_info=_to_contact_info(patient.contact_info),
        status=patient.status,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
        archived_at=patient.archived_at,
        consents=[
            ConsentRead(
                id=consent.id,
                type=consent.type,
                status=consent.status,
                granted_at=consent.granted_at,
                revoked_at=consent.revoked_at,
                notes=consent.notes,
            )
            for consent in consents
        ],
        contacts=[
            PatientContactRead(
                id=contact.id,
                name=contact.name,
                relationship=contact.relationship,
                phone=contact.phone,
                email=contact.email,
                is_guardian=contact.is_guardian,
            )
            for contact in contacts
        ],
        history=[
            PatientHistoryRead(
                id=history.id,
                changed_at=history.changed_at,
                changed_by=history.changed_by,
                change_type=history.change_type,
                reason=history.reason,
            )
            for history in history_entries
        ],
    )


def _build_patient_summary(patient: Patient) -> PatientSummary:
    full_name = f"{patient.first_name} {patient.last_name}".strip()
    return PatientSummary(
        id=patient.id,
        identifier=patient.identifier,
        full_name=full_name,
        date_of_birth=patient.date_of_birth,
        status=patient.status,
        updated_at=patient.updated_at,
    )


def _serialize_conflict_patient(patient: Patient, match_type: str) -> Dict[str, object]:
    return {
        "match_type": match_type,
        "patient": {
            "id": patient.id,
            "identifier": patient.identifier,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            "sex": patient.sex,
            "status": patient.status,
        },
    }


def _find_duplicate_patients(
    session: Session,
    *,
    identifier: Optional[str],
    date_of_birth: Optional[date],
    sex: Optional[str],
    exclude_id: Optional[int] = None,
) -> List[Dict[str, object]]:
    duplicates: List[Dict[str, object]] = []
    seen: Set[int] = set()

    if identifier:
        existing = session.exec(select(Patient).where(Patient.identifier == identifier)).first()
        if existing and existing.id != exclude_id:
            duplicates.append(_serialize_conflict_patient(existing, "identifier"))
            seen.add(existing.id)

    if date_of_birth and sex:
        normalized_sex = sex.lower()
        matches = session.exec(
            select(Patient).where(
                Patient.date_of_birth == date_of_birth,
                func.lower(Patient.sex) == normalized_sex,
            )
        ).all()
        for match in matches:
            if match.id == exclude_id or match.id in seen:
                continue
            duplicates.append(_serialize_conflict_patient(match, "demographics"))
            seen.add(match.id)

    return duplicates


def _merge_contact_info(target: dict, source: dict) -> dict:
    merged = dict(target)
    for key, value in source.items():
        current = merged.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            merged[key] = _merge_contact_info(current, value)
        elif not current:
            merged[key] = value
    return merged


def _contact_signature(contact: PatientContact) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
    return (
        contact.name.strip().lower(),
        contact.relationship.strip().lower() if contact.relationship else None,
        contact.phone.strip() if contact.phone else None,
        contact.email.strip().lower() if contact.email else None,
    )


def _consent_signature(
    consent: Consent,
) -> Tuple[str, str, Optional[datetime], Optional[datetime], Optional[str]]:
    return (
        consent.type,
        consent.status,
        consent.granted_at,
        consent.revoked_at,
        consent.notes,
    )


def list_patients(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 25,
    search: Optional[str] = None,
    status: Optional[str] = None,
) -> Tuple[List[PatientSummary], int]:
    statement = select(Patient)
    count_stmt = select(func.count()).select_from(Patient)

    if status:
        statement = statement.where(Patient.status == status)
        count_stmt = count_stmt.where(Patient.status == status)

    if search:
        pattern = f"%{search.lower()}%"
        full_name = func.lower(func.concat(Patient.first_name, ' ', Patient.last_name))
        search_filter = or_(
            func.lower(Patient.first_name).like(pattern),
            func.lower(Patient.last_name).like(pattern),
            full_name.like(pattern),
            func.lower(func.coalesce(Patient.identifier, '')).like(pattern),
        )
        statement = statement.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    statement = statement.order_by(Patient.updated_at.desc())
    total = session.exec(count_stmt).one()
    patients = session.exec(
        statement.offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [_build_patient_summary(patient) for patient in patients], total


def get_patient(session: Session, patient_id: int) -> PatientRead:
    patient = session.get(Patient, patient_id)
    if not patient:
        raise PatientNotFoundError
    return _build_patient_read(session, patient)


def _apply_patient_contacts(
    session: Session, patient_id: int, contacts: List[PatientContactCreate]
) -> None:
    existing = session.exec(select(PatientContact).where(PatientContact.patient_id == patient_id)).all()
    for contact in existing:
        session.delete(contact)
    for contact in contacts:
        session.add(
            PatientContact(
                patient_id=patient_id,
                name=contact.name,
                relationship=contact.relationship,
                phone=contact.phone,
                email=contact.email,
                is_guardian=contact.is_guardian,
            )
        )


def _apply_patient_consents(
    session: Session, patient_id: int, consents_data: List[ConsentCreate]
) -> None:
    existing = session.exec(select(Consent).where(Consent.patient_id == patient_id)).all()
    for consent in existing:
        session.delete(consent)
    for consent in consents_data:
        session.add(
            Consent(
                patient_id=patient_id,
                type=consent.type,
                status=consent.status,
                granted_at=consent.granted_at,
                revoked_at=consent.revoked_at,
                notes=consent.notes,
            )
        )


def create_patient(
    session: Session,
    *,
    data: PatientCreate,
    actor_id: Optional[int],
    context: Optional[dict] = None,
) -> PatientRead:
    duplicates = _find_duplicate_patients(
        session,
        identifier=data.identifier,
        date_of_birth=data.date_of_birth,
        sex=data.sex,
    )
    if duplicates:
        raise PatientConflictError("PATIENT_DUPLICATE", payload={"matches": duplicates})

    patient = Patient(
        identifier=data.identifier,
        first_name=data.first_name,
        last_name=data.last_name,
        date_of_birth=data.date_of_birth,
        sex=data.sex,
        language=data.language,
        contact_info=data.contact_info.model_dump(exclude_none=True) if data.contact_info else {},
        status=data.status or "active",
        created_by=actor_id,
    )
    session.add(patient)
    session.flush()

    _apply_patient_consents(session, patient.id, data.consents)
    _apply_patient_contacts(session, patient.id, data.contacts)

    history_entry = PatientHistory(
        patient_id=patient.id,
        changed_by=actor_id,
        change_type="create",
        snapshot=patient.model_dump(mode="json"),
        reason="Luonti",
    )
    session.add(history_entry)

    audit.record_event(
        session,
        actor_id=actor_id,
        action="patient.create",
        resource_type="patient",
        resource_id=str(patient.id),
        metadata={"identifier": patient.identifier},
        context=context or {},
    )

    session.commit()
    session.refresh(patient)
    return _build_patient_read(session, patient)


def merge_patients(
    session: Session,
    *,
    target_patient_id: int,
    source_patient_id: int,
    actor_id: Optional[int],
    context: Optional[dict] = None,
) -> PatientRead:
    if target_patient_id == source_patient_id:
        raise PatientMergeError(
            "MERGE_SAME_PATIENT",
            "Lähde- ja kohdepotilas ovat samat",
        )

    target = session.get(Patient, target_patient_id)
    if not target:
        raise PatientNotFoundError

    source = session.get(Patient, source_patient_id)
    if not source:
        raise PatientNotFoundError

    target_contacts = session.exec(
        select(PatientContact).where(PatientContact.patient_id == target_patient_id)
    ).all()
    source_contacts = session.exec(
        select(PatientContact).where(PatientContact.patient_id == source_patient_id)
    ).all()

    contact_signatures = {_contact_signature(contact) for contact in target_contacts}
    for contact in source_contacts:
        signature = _contact_signature(contact)
        if signature in contact_signatures:
            session.delete(contact)
            continue
        contact.patient_id = target_patient_id
        contact_signatures.add(signature)

    target_consents = session.exec(
        select(Consent).where(Consent.patient_id == target_patient_id)
    ).all()
    source_consents = session.exec(
        select(Consent).where(Consent.patient_id == source_patient_id)
    ).all()

    consent_signatures = {_consent_signature(consent) for consent in target_consents}
    for consent in source_consents:
        signature = _consent_signature(consent)
        if signature in consent_signatures:
            session.delete(consent)
            continue
        consent.patient_id = target_patient_id
        consent_signatures.add(signature)

    history_entries = session.exec(
        select(PatientHistory).where(PatientHistory.patient_id == source_patient_id)
    ).all()
    for history in history_entries:
        history.patient_id = target_patient_id

    target.contact_info = _merge_contact_info(target.contact_info or {}, source.contact_info or {})
    target.updated_at = datetime.utcnow()

    merge_reason = f"Yhdistetty potilaasta {source_patient_id}"
    merge_history = PatientHistory(
        patient_id=target.id,
        changed_by=actor_id,
        change_type="merge",
        snapshot=target.model_dump(mode="json"),
        reason=merge_reason,
    )
    session.add(merge_history)

    source_history = PatientHistory(
        patient_id=source.id,
        changed_by=actor_id,
        change_type="merge_source",
        snapshot=source.model_dump(mode="json"),
        reason=f"Yhdistetty potilaaseen {target_patient_id}",
    )
    session.add(source_history)

    source.identifier = None
    source.status = "archived"
    source.archived_at = datetime.utcnow()
    source.updated_at = datetime.utcnow()

    audit.record_event(
        session,
        actor_id=actor_id,
        action="patient.merge",
        resource_type="patient",
        resource_id=str(target.id),
        metadata={"source_patient_id": source_patient_id},
        context=context or {},
    )

    audit.record_event(
        session,
        actor_id=actor_id,
        action="patient.merge.archived",
        resource_type="patient",
        resource_id=str(source.id),
        metadata={"merged_into": target_patient_id},
        context=context or {},
    )

    session.commit()
    session.refresh(target)
    return _build_patient_read(session, target)


def update_patient(
    session: Session,
    *,
    patient_id: int,
    data: PatientCreate,
    actor_id: Optional[int],
    reason: Optional[str] = None,
    context: Optional[dict] = None,
) -> PatientRead:
    patient = session.get(Patient, patient_id)
    if not patient:
        raise PatientNotFoundError

    duplicates = _find_duplicate_patients(
        session,
        identifier=data.identifier,
        date_of_birth=data.date_of_birth,
        sex=data.sex,
        exclude_id=patient.id,
    )
    if duplicates:
        raise PatientConflictError("PATIENT_DUPLICATE", payload={"matches": duplicates})

    patient.identifier = data.identifier
    patient.first_name = data.first_name
    patient.last_name = data.last_name
    patient.date_of_birth = data.date_of_birth
    patient.sex = data.sex
    patient.language = data.language
    patient.contact_info = data.contact_info.model_dump(exclude_none=True) if data.contact_info else {}
    patient.status = data.status or patient.status
    patient.updated_at = datetime.utcnow()

    _apply_patient_consents(session, patient.id, data.consents)
    _apply_patient_contacts(session, patient.id, data.contacts)

    history_entry = PatientHistory(
        patient_id=patient.id,
        changed_by=actor_id,
        change_type="update",
        snapshot=patient.model_dump(mode="json"),
        reason=reason,
    )
    session.add(history_entry)

    audit.record_event(
        session,
        actor_id=actor_id,
        action="patient.update",
        resource_type="patient",
        resource_id=str(patient.id),
        metadata={"identifier": patient.identifier},
        context=context or {},
    )

    session.commit()
    session.refresh(patient)
    return _build_patient_read(session, patient)


def patch_patient(
    session: Session,
    *,
    patient_id: int,
    data: PatientUpdate,
    actor_id: Optional[int],
    context: Optional[dict] = None,
) -> PatientRead:
    patient = session.get(Patient, patient_id)
    if not patient:
        raise PatientNotFoundError

    identifier = data.identifier if data.identifier is not None else patient.identifier
    date_of_birth = data.date_of_birth if data.date_of_birth is not None else patient.date_of_birth
    sex = data.sex if data.sex is not None else patient.sex

    duplicates = _find_duplicate_patients(
        session,
        identifier=identifier,
        date_of_birth=date_of_birth,
        sex=sex,
        exclude_id=patient.id,
    )
    if duplicates:
        raise PatientConflictError("PATIENT_DUPLICATE", payload={"matches": duplicates})

    if data.identifier is not None:
        patient.identifier = data.identifier

    if data.first_name is not None:
        patient.first_name = data.first_name
    if data.last_name is not None:
        patient.last_name = data.last_name
    if data.date_of_birth is not None:
        patient.date_of_birth = data.date_of_birth
    if data.sex is not None:
        patient.sex = data.sex
    if data.language is not None:
        patient.language = data.language
    if data.contact_info is not None:
        patient.contact_info = data.contact_info.model_dump(exclude_none=True)
    if data.status is not None:
        patient.status = data.status
    patient.updated_at = datetime.utcnow()

    if data.consents is not None:
        _apply_patient_consents(session, patient.id, data.consents)
    if data.contacts is not None:
        _apply_patient_contacts(session, patient.id, data.contacts)

    history_entry = PatientHistory(
        patient_id=patient.id,
        changed_by=actor_id,
        change_type="patch",
        snapshot=patient.model_dump(mode="json"),
        reason=data.reason,
    )
    session.add(history_entry)

    audit.record_event(
        session,
        actor_id=actor_id,
        action="patient.patch",
        resource_type="patient",
        resource_id=str(patient.id),
        metadata={"identifier": patient.identifier},
        context=context or {},
    )

    session.commit()
    session.refresh(patient)
    return _build_patient_read(session, patient)


def archive_patient(
    session: Session,
    *,
    patient_id: int,
    actor_id: Optional[int],
    reason: Optional[str] = None,
    context: Optional[dict] = None,
) -> None:
    patient = session.get(Patient, patient_id)
    if not patient:
        raise PatientNotFoundError
    patient.status = "archived"
    patient.archived_at = datetime.utcnow()
    patient.updated_at = datetime.utcnow()

    history_entry = PatientHistory(
        patient_id=patient.id,
        changed_by=actor_id,
        change_type="archive",
        snapshot=patient.model_dump(mode="json"),
        reason=reason or "Arkistointi",
    )
    session.add(history_entry)

    audit.record_event(
        session,
        actor_id=actor_id,
        action="patient.archive",
        resource_type="patient",
        resource_id=str(patient.id),
        metadata={"identifier": patient.identifier},
        context=context or {},
    )

    session.commit()
