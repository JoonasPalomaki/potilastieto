from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict

import pytest

pytest.importorskip("httpx")

from fastapi.testclient import TestClient
from sqlalchemy import func, text
from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.main import app
from app.models import Appointment, AuditEvent, Role, User
from app.schemas import PatientCreate
from app.services import audit, create_patient
from app.services.security import create_access_token


@pytest.fixture
def audit_api_context() -> Dict[str, object]:
    init_db()
    with Session(engine) as session:
        tables = [
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
            session.exec(text(f"DELETE FROM {table}"))
        session.commit()

        roles = {
            "admin": Role(
                code="admin",
                name="Admin",
                permissions=[
                    "patients:read",
                    "patients:write",
                    "appointments:write",
                    "audit:read",
                    "admin:manage",
                ],
            ),
            "doctor": Role(
                code="doctor",
                name="Doctor",
                permissions=["patients:read", "patients:write", "appointments:write"],
            ),
            "nurse": Role(
                code="nurse",
                name="Nurse",
                permissions=["patients:read", "patients:write", "appointments:write"],
            ),
        }
        session.add_all(roles.values())
        session.commit()

        admin = User(
            username="admin.audit",
            password_hash="!",
            display_name="Admin Audit",
            role_id=roles["admin"].id,
            is_active=True,
        )
        doctor = User(
            username="doctor.audit",
            password_hash="!",
            display_name="Doctor Audit",
            role_id=roles["doctor"].id,
            is_active=True,
        )
        nurse = User(
            username="nurse.audit",
            password_hash="!",
            display_name="Nurse Audit",
            role_id=roles["nurse"].id,
            is_active=True,
        )
        session.add(admin)
        session.add(doctor)
        session.add(nurse)
        session.commit()
        session.refresh(admin)
        session.refresh(doctor)
        session.refresh(nurse)

        patient_one = create_patient(
            session,
            data=PatientCreate(
                identifier="131052-308T",
                first_name="Audit",
                last_name="PatientOne",
            ),
            actor_id=doctor.id,
            context={},
        )
        patient_two = create_patient(
            session,
            data=PatientCreate(
                identifier="131052-302L",
                first_name="Audit",
                last_name="PatientTwo",
            ),
            actor_id=doctor.id,
            context={},
        )

        now = datetime.utcnow()
        appointment = Appointment(
            patient_id=patient_one.id,
            provider_id=doctor.id,
            service_type="checkup",
            location="Room 5",
            start_time=now,
            end_time=now + timedelta(minutes=30),
            status="scheduled",
            created_by=doctor.id,
        )
        session.add(appointment)
        session.commit()
        session.refresh(appointment)

        for index in range(105):
            audit.record_event(
                session,
                actor_id=doctor.id,
                action="patient.read",
                resource_type="patient",
                resource_id=str(patient_one.id),
                metadata={"index": index},
                context={"request_id": f"req-{index}"},
            )
        for index in range(5):
            audit.record_event(
                session,
                actor_id=doctor.id,
                action="patient.read",
                resource_type="patient",
                resource_id=str(patient_two.id),
                metadata={"index": index},
                context={"request_id": f"other-{index}"},
            )

        audit.record_event(
            session,
            actor_id=doctor.id,
            action="appointment.read",
            resource_type="appointment",
            resource_id=str(appointment.id),
            metadata={"patient_id": patient_one.id},
            context={"request_id": "appt-read"},
        )

        session.commit()

        patient_one_events = session.exec(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.resource_type == "patient",
                AuditEvent.resource_id == str(patient_one.id),
            )
        ).one()

        context: Dict[str, object] = {
            "client": None,
            "doctor_token": create_access_token(str(doctor.id), {"role": "doctor"}),
            "nurse_token": create_access_token(str(nurse.id), {"role": "nurse"}),
            "admin_token": create_access_token(str(admin.id), {"role": "admin"}),
            "patient_one_id": patient_one.id,
            "patient_two_id": patient_two.id,
            "appointment_id": appointment.id,
            "patient_one_event_count": int(patient_one_events),
        }

    with TestClient(app) as client:
        context["client"] = client
        yield context


def test_doctor_requires_filters(audit_api_context: Dict[str, object]) -> None:
    client: TestClient = audit_api_context["client"]
    headers = {"Authorization": f"Bearer {audit_api_context['doctor_token']}"}

    response = client.get("/api/v1/audit/", headers=headers)
    assert response.status_code == 400
    assert "resource_id" in response.json()["detail"]


def test_doctor_rejects_invalid_resource_type(audit_api_context: Dict[str, object]) -> None:
    client: TestClient = audit_api_context["client"]
    headers = {"Authorization": f"Bearer {audit_api_context['doctor_token']}"}

    response = client.get(
        "/api/v1/audit/",
        params={"resource_type": "system", "resource_id": "123"},
        headers=headers,
    )
    assert response.status_code == 400
    assert "patient" in response.json()["detail"]


def test_doctor_paginated_results_filtered(audit_api_context: Dict[str, object]) -> None:
    client: TestClient = audit_api_context["client"]
    headers = {"Authorization": f"Bearer {audit_api_context['doctor_token']}"}

    params = {
        "resource_type": "patient",
        "resource_id": str(audit_api_context["patient_one_id"]),
        "page_size": 200,
    }
    response = client.get("/api/v1/audit/", params=params, headers=headers)
    assert response.status_code == 200
    body = response.json()

    assert body["page_size"] == 200
    assert body["total"] == audit_api_context["patient_one_event_count"]
    assert len(body["items"]) == min(100, body["total"])
    assert all(
        item["resource_id"] == str(audit_api_context["patient_one_id"]) for item in body["items"]
    )

    response_page_two = client.get(
        "/api/v1/audit/",
        params={**params, "page": 2},
        headers=headers,
    )
    assert response_page_two.status_code == 200
    page_two_items = response_page_two.json()["items"]
    expected_remaining = max(0, body["total"] - 100)
    assert len(page_two_items) == expected_remaining
    assert all(
        item["resource_id"] == str(audit_api_context["patient_one_id"]) for item in page_two_items
    )


def test_doctor_csv_export(audit_api_context: Dict[str, object]) -> None:
    client: TestClient = audit_api_context["client"]
    headers = {"Authorization": f"Bearer {audit_api_context['doctor_token']}"}

    response = client.get(
        "/api/v1/audit/",
        params={
            "resource_type": "patient",
            "resource_id": str(audit_api_context["patient_one_id"]),
            "page_size": 50,
            "format": "csv",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")

    lines = [line for line in response.text.strip().splitlines() if line]
    assert lines[0].startswith("id,timestamp,actor_id")
    # header plus number of returned rows
    assert len(lines) == min(50, audit_api_context["patient_one_event_count"]) + 1


def test_doctor_rejects_unknown_format(audit_api_context: Dict[str, object]) -> None:
    client: TestClient = audit_api_context["client"]
    headers = {"Authorization": f"Bearer {audit_api_context['doctor_token']}"}

    response = client.get(
        "/api/v1/audit/",
        params={
            "resource_type": "patient",
            "resource_id": str(audit_api_context["patient_one_id"]),
            "format": "xml",
        },
        headers=headers,
    )
    assert response.status_code == 400
    assert "Unsupported format" in response.json()["detail"]


def test_nurse_can_view_appointment_events(audit_api_context: Dict[str, object]) -> None:
    client: TestClient = audit_api_context["client"]
    headers = {"Authorization": f"Bearer {audit_api_context['nurse_token']}"}

    response = client.get(
        "/api/v1/audit/",
        params={
            "resource_type": "appointment",
            "resource_id": str(audit_api_context["appointment_id"]),
        },
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["resource_id"] == str(audit_api_context["appointment_id"])


def test_admin_can_list_without_filters(audit_api_context: Dict[str, object]) -> None:
    client: TestClient = audit_api_context["client"]
    headers = {"Authorization": f"Bearer {audit_api_context['admin_token']}"}

    response = client.get("/api/v1/audit/", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] >= audit_api_context["patient_one_event_count"]
