from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

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
    pass


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
    if data.identifier:
        existing = session.exec(select(Patient).where(Patient.identifier == data.identifier)).first()
        if existing:
            raise PatientConflictError("IDENTIFIER_EXISTS")

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
        snapshot=patient.dict(),
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
    if data.identifier and data.identifier != patient.identifier:
        existing = session.exec(select(Patient).where(Patient.identifier == data.identifier)).first()
        if existing and existing.id != patient.id:
            raise PatientConflictError("IDENTIFIER_EXISTS")

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
        snapshot=patient.dict(),
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

    if data.identifier and data.identifier != patient.identifier:
        existing = session.exec(select(Patient).where(Patient.identifier == data.identifier)).first()
        if existing and existing.id != patient.id:
            raise PatientConflictError("IDENTIFIER_EXISTS")
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
        snapshot=patient.dict(),
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
        snapshot=patient.dict(),
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
