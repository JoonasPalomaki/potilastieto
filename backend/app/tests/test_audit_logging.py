from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

import pytest
from sqlalchemy import text
from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.models import Appointment, AuditEvent, Role, User
from app.schemas import PatientCreate
from app.services import audit, create_patient, get_patient, list_appointments
from app.services.audit_policy import hash_identifier, make_patient_reference


@pytest.fixture
def session() -> Session:
    init_db()
    with Session(engine) as db_session:
        tables: List[str] = [
            "audit_events",
            "appointment_status_history",
            "appointments",
            "refresh_tokens",
            "visits",
            "orders",
            "clinical_notes",
            "lab_results",
            "diagnosis_codes",
            "patient_history",
            "consents",
            "patient_contacts",
            "patients",
            "users",
            "roles",
        ]
        for table in tables:
            db_session.exec(text(f"DELETE FROM {table}"))
        db_session.commit()
        roles = [
            Role(
                code="doctor",
                name="Doctor",
                permissions=["patients:read", "patients:write", "appointments:write"],
            )
        ]
        for role in roles:
            db_session.add(role)
        db_session.commit()
        yield db_session
        db_session.rollback()


def _create_user(session: Session, role_code: str, username: str) -> User:
    role = session.exec(select(Role).where(Role.code == role_code)).one()
    user = User(
        username=username,
        password_hash="!",
        display_name=f"{username.title()} User",
        role_id=role.id,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_get_patient_logs_audit_event(session: Session) -> None:
    doctor = _create_user(session, "doctor", "doctor-reader")

    patient = create_patient(
        session,
        data=PatientCreate(
            identifier="131052-308T",
            first_name="Test",
            last_name="Potilas",
        ),
        actor_id=doctor.id,
        context={},
    )

    context: Dict[str, str] = {"request_id": "svc-test"}
    result = get_patient(
        session,
        patient.id,
        audit_actor_id=doctor.id,
        audit_context=context,
    )

    assert result.id == patient.id

    events = (
        session.exec(
            select(AuditEvent).where(
                AuditEvent.action == "patient.read",
                AuditEvent.resource_id == str(patient.id),
            )
        ).all()
    )
    assert len(events) == 1
    event = events[0]
    assert event.actor_id == doctor.id
    assert event.context.get("request_id") == "svc-test"


def test_list_appointments_logs_all_items(session: Session) -> None:
    doctor = _create_user(session, "doctor", "doctor-audit")
    patient = create_patient(
        session,
        data=PatientCreate(
            identifier="131052-302L",
            first_name="Audit",
            last_name="Patient",
        ),
        actor_id=doctor.id,
        context={},
    )

    now = datetime.utcnow()
    appointments: List[Appointment] = []
    for index in range(2):
        appointment = Appointment(
            patient_id=patient.id,
            provider_id=doctor.id,
            service_type="checkup",
            location="Room 1",
            start_time=now + timedelta(hours=index),
            end_time=now + timedelta(hours=index, minutes=30),
            status="scheduled",
            created_by=doctor.id,
        )
        session.add(appointment)
        appointments.append(appointment)
    session.commit()
    for appointment in appointments:
        session.refresh(appointment)

    context: Dict[str, str] = {"request_id": "list-test"}
    items, total = list_appointments(
        session,
        page=1,
        page_size=10,
        patient_id=patient.id,
        audit_actor_id=doctor.id,
        audit_context=context,
    )

    assert total == len(items) == len(appointments)

    events = session.exec(
        select(AuditEvent).where(AuditEvent.action == "appointment.list")
    ).all()
    assert len(events) == len(appointments)
    resource_ids = {event.resource_id for event in events}
    expected_ids = {str(appointment.id) for appointment in appointments}
    assert resource_ids == expected_ids
    for event in events:
        assert event.actor_id == doctor.id
        assert event.context.get("request_id") == "list-test"
        assert event.metadata_json.get("result_count") == len(appointments)
        assert event.metadata_json.get("patient_ref") == make_patient_reference(patient.id)


def test_patient_audit_metadata_uses_hashed_identifier(session: Session) -> None:
    doctor = _create_user(session, "doctor", "doctor-meta")
    patient = create_patient(
        session,
        data=PatientCreate(
            identifier="131052-308T",
            first_name="Meta",
            last_name="Audit",
        ),
        actor_id=doctor.id,
        context={},
    )

    events = session.exec(
        select(AuditEvent)
        .where(
            AuditEvent.action == "patient.create",
            AuditEvent.resource_type == "patient",
            AuditEvent.resource_id == str(patient.id),
        )
        .order_by(AuditEvent.timestamp)
    ).all()
    assert events
    identifier_tokens = {event.metadata_json.get("identifier_token") for event in events}
    expected_token = hash_identifier(patient.identifier)
    assert expected_token in identifier_tokens
    assert patient.identifier not in identifier_tokens


def test_audit_rejects_direct_hetu_metadata(session: Session) -> None:
    doctor = _create_user(session, "doctor", "doctor-hetu")

    with pytest.raises(ValueError):
        audit.record_event(
            session,
            actor_id=doctor.id,
            action="patient.test",
            resource_type="patient",
            resource_id="1",
            metadata={"identifier": "131052-308T"},
            context={},
        )


def test_diagnosis_import_metadata_allowed(session: Session) -> None:
    doctor = _create_user(session, "doctor", "doctor-import")

    audit.record_event(
        session,
        actor_id=doctor.id,
        action="diagnosis_code.import",
        resource_type="diagnosis_code",
        resource_id=None,
        metadata={
            "filename": "codes.csv",
            "total_rows": 2,
            "inserted": 2,
            "updated": 0,
            "marked_deleted": 1,
            "skipped": 0,
            "error_count": 0,
        },
        context={"request_id": "diag-test"},
    )


def test_audit_rejects_unapproved_metadata_key(session: Session) -> None:
    doctor = _create_user(session, "doctor", "doctor-unexpected")

    with pytest.raises(ValueError):
        audit.record_event(
            session,
            actor_id=doctor.id,
            action="patient.test",
            resource_type="patient",
            resource_id="1",
            metadata={"unexpected": "value"},
            context={},
        )
