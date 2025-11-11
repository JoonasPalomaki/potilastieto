from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict

import pytest

pytest.importorskip("httpx")

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.main import app
from app.models import Role, User
from app.schemas import AppointmentCreate, AppointmentRescheduleRequest, PatientCreate
from app.services import create_patient, ensure_seed_data, security


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def appointment_api_context() -> Dict[str, object]:
    init_db()
    with Session(engine) as session:
        session.exec(text("DELETE FROM appointment_status_history"))
        session.exec(text("DELETE FROM appointments"))
        session.exec(text("DELETE FROM audit_events"))
        session.exec(text("DELETE FROM patient_contacts"))
        session.exec(text("DELETE FROM consents"))
        session.exec(text("DELETE FROM patients"))
        session.exec(text("DELETE FROM users"))
        session.exec(text("DELETE FROM roles"))
        session.commit()

        ensure_seed_data(session)

        doctor_password = "doctorpass"
        doctor_role = session.exec(select(Role).where(Role.code == "doctor")).one()
        doctor = User(
            username="doctor",
            password_hash=security.hash_password(doctor_password),
            display_name="Tohtori Testi",
            role_id=doctor_role.id,
        )
        session.add(doctor)
        session.commit()
        session.refresh(doctor)

        patient = create_patient(
            session,
            data=PatientCreate(
                identifier="131052-308T",
                first_name="Test",
                last_name="Potilas",
                contact_info={"email": "test@example.com"},
            ),
            actor_id=doctor.id,
            context={},
        )

        context: Dict[str, object] = {
            "doctor_username": doctor.username,
            "doctor_password": doctor_password,
            "doctor_id": doctor.id,
            "patient_id": patient.id,
        }

    with TestClient(app) as client:
        context["client"] = client
        yield context


def test_availability_endpoint_returns_slots(appointment_api_context: Dict[str, object]) -> None:
    client: TestClient = appointment_api_context["client"]
    token = _login(client, appointment_api_context["doctor_username"], appointment_api_context["doctor_password"])
    headers = {"Authorization": f"Bearer {token}"}

    start = datetime(2024, 2, 1, 9, 0)
    create_payload = AppointmentCreate(
        patient_id=appointment_api_context["patient_id"],
        provider_id=appointment_api_context["doctor_id"],
        location="Room 1",
        start_time=start,
        end_time=start + timedelta(minutes=30),
    )

    response = client.post("/api/v1/appointments/", json=create_payload.model_dump(mode="json"), headers=headers)
    assert response.status_code == 201

    availability_response = client.get(
        "/api/v1/appointments/availability",
        params={
            "provider_id": appointment_api_context["doctor_id"],
            "start_from": start.isoformat(),
            "end_to": (start + timedelta(hours=3)).isoformat(),
            "slot_minutes": 30,
        },
        headers=headers,
    )
    assert availability_response.status_code == 200
    payload = availability_response.json()
    assert payload
    first_entry = payload[0]
    assert first_entry["provider_id"] == appointment_api_context["doctor_id"]
    slot_starts = {slot["start_time"] for slot in first_entry["slots"]}
    assert start.isoformat() not in slot_starts


def test_reschedule_endpoint_provides_alternatives(appointment_api_context: Dict[str, object]) -> None:
    client: TestClient = appointment_api_context["client"]
    token = _login(client, appointment_api_context["doctor_username"], appointment_api_context["doctor_password"])
    headers = {"Authorization": f"Bearer {token}"}

    base_start = datetime(2024, 3, 1, 9, 0)

    create_response = client.post(
        "/api/v1/appointments/",
        json=AppointmentCreate(
            patient_id=appointment_api_context["patient_id"],
            provider_id=appointment_api_context["doctor_id"],
            location="Room 2",
            start_time=base_start,
            end_time=base_start + timedelta(minutes=30),
        ).model_dump(mode="json"),
        headers=headers,
    )
    assert create_response.status_code == 201
    appointment_id = create_response.json()["id"]

    conflict_response = client.post(
        "/api/v1/appointments/",
        json=AppointmentCreate(
            patient_id=appointment_api_context["patient_id"],
            provider_id=appointment_api_context["doctor_id"],
            location="Room 2",
            start_time=base_start + timedelta(hours=1),
            end_time=base_start + timedelta(hours=1, minutes=30),
        ).model_dump(mode="json"),
        headers=headers,
    )
    assert conflict_response.status_code == 201

    reschedule_response = client.post(
        f"/api/v1/appointments/{appointment_id}/reschedule",
        json=AppointmentRescheduleRequest(
            start_time=base_start + timedelta(hours=1),
            end_time=base_start + timedelta(hours=1, minutes=30),
            reason="Requested",
        ).model_dump(mode="json"),
        headers=headers,
    )
    assert reschedule_response.status_code == 409
    body = reschedule_response.json()["detail"]
    assert body["code"] == "PROVIDER_OVERLAP"
    assert body["alternatives"]


def test_reschedule_endpoint_updates_slot(appointment_api_context: Dict[str, object]) -> None:
    client: TestClient = appointment_api_context["client"]
    token = _login(client, appointment_api_context["doctor_username"], appointment_api_context["doctor_password"])
    headers = {"Authorization": f"Bearer {token}"}

    base_start = datetime(2024, 3, 2, 9, 0)

    create_response = client.post(
        "/api/v1/appointments/",
        json=AppointmentCreate(
            patient_id=appointment_api_context["patient_id"],
            provider_id=appointment_api_context["doctor_id"],
            location="Room 2",
            start_time=base_start,
            end_time=base_start + timedelta(minutes=30),
        ).model_dump(mode="json"),
        headers=headers,
    )
    assert create_response.status_code == 201
    appointment_id = create_response.json()["id"]

    reschedule_response = client.post(
        f"/api/v1/appointments/{appointment_id}/reschedule",
        json=AppointmentRescheduleRequest(
            start_time=base_start + timedelta(hours=2),
            end_time=base_start + timedelta(hours=2, minutes=30),
            reason="Available",
        ).model_dump(mode="json"),
        headers=headers,
    )
    assert reschedule_response.status_code == 200
    body = reschedule_response.json()
    assert body["start_time"].startswith((base_start + timedelta(hours=2)).isoformat())
