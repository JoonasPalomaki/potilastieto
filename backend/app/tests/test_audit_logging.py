from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

import pytest
from sqlalchemy import text
from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.models import Appointment, AuditEvent, Role, User
from app.schemas import PatientCreate
from app.services import create_patient, get_patient, list_appointments


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
        assert event.metadata_json.get("patient_id") == patient.id
