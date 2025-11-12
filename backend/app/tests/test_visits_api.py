from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict

import pytest

pytest.importorskip("httpx")

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.main import app
from app.models import Appointment, AuditEvent, Role, User
from app.schemas import InitialVisitCreate, PatientCreate
from app.services import create_patient, ensure_seed_data, security


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    body = response.json()
    return body["access_token"]


@pytest.fixture()
def visit_api_context() -> Dict[str, object]:
    init_db()
    with Session(engine) as session:
        session.exec(text("DELETE FROM refresh_tokens"))
        session.exec(text("DELETE FROM audit_events"))
        session.exec(text("DELETE FROM lab_results"))
        session.exec(text("DELETE FROM orders"))
        session.exec(text("DELETE FROM clinical_notes"))
        session.exec(text("DELETE FROM visits"))
        session.exec(text("DELETE FROM appointments"))
        session.exec(text("DELETE FROM patient_history"))
        session.exec(text("DELETE FROM consents"))
        session.exec(text("DELETE FROM patient_contacts"))
        session.exec(text("DELETE FROM patients"))
        session.exec(text("DELETE FROM users"))
        session.exec(text("DELETE FROM roles"))
        session.commit()

        ensure_seed_data(session)

        doctor_role = session.exec(select(Role).where(Role.code == "doctor")).one()
        doctor_password = "doctorpass"
        doctor = User(
            username="drvisit",
            password_hash=security.hash_password(doctor_password),
            display_name="Lääkäri Käynti",
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
                date_of_birth=date(1952, 10, 13),
                sex="female",
            ),
            actor_id=doctor.id,
            context={},
        )

        start_time = datetime.utcnow()
        appointment = Appointment(
            patient_id=patient.id,
            provider_id=doctor.id,
            location="Klinikka A",
            service_type="Ensikäynti",
            start_time=start_time,
            end_time=start_time + timedelta(hours=1),
            status="scheduled",
            created_by=doctor.id,
        )
        session.add(appointment)
        session.commit()
        session.refresh(appointment)

        context: Dict[str, object] = {
            "doctor_username": doctor.username,
            "doctor_password": doctor_password,
            "patient_id": patient.id,
            "appointment_id": appointment.id,
        }

    with TestClient(app) as client:
        context["client"] = client
        yield context


def _create_visit(client: TestClient, headers: Dict[str, str], context: Dict[str, object]) -> int:
    payload = InitialVisitCreate(
        appointment_id=context["appointment_id"],
        basics={"location": "Huone 1"},
        reason={"reason": "Päänsärky"},
        anamnesis={"content": "Potilas raportoi toistuvaa päänsärkyä."},
        status={"content": "Yleistila hyvä."},
        diagnoses={"diagnoses": [{"code": "R51", "description": "Päänsärky"}]},
        orders={
            "orders": [
                {
                    "order_type": "laboratory",
                    "status": "ordered",
                    "details": {"test": "CRP"},
                }
            ]
        },
        summary={"content": "Seuranta viikon kuluttua."},
    ).model_dump(mode="json")
    response = client.post("/api/v1/visits", headers=headers, json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()["id"]


def test_create_visit_success(visit_api_context: Dict[str, object]) -> None:
    client: TestClient = visit_api_context["client"]
    token = _login(client, visit_api_context["doctor_username"], visit_api_context["doctor_password"])
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "appointment_id": visit_api_context["appointment_id"],
        "basics": {"location": "Huone 2", "visit_type": "initial"},
        "reason": {"reason": "Päänsärky"},
        "anamnesis": {"content": "Potilas raportoi toistuvaa päänsärkyä."},
        "status": {"content": "Yleistila hyvä."},
        "diagnoses": {"diagnoses": [{"code": "R51", "description": "Päänsärky"}]},
        "orders": {
            "orders": [
                {
                    "order_type": "laboratory",
                    "status": "ordered",
                    "details": {"test": "CRP"},
                }
            ]
        },
        "summary": {"content": "Seuranta viikon kuluttua."},
    }

    response = client.post("/api/v1/visits", headers=headers, json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()

    assert body["patient_id"] == visit_api_context["patient_id"]
    assert body["basics"]["location"] == "Huone 2"
    assert body["diagnoses"]["diagnoses"][0]["code"] == "R51"
    assert body["orders"]["orders"], "Expected orders to be stored"

    with Session(engine) as session:
        events = session.exec(
            select(AuditEvent).where(AuditEvent.action == "visit.create")
        ).all()

    assert len(events) == 1
    assert events[0].metadata_json.get("patient_ref") == f"patient:{visit_api_context['patient_id']}"


def test_anamnesis_requires_content(visit_api_context: Dict[str, object]) -> None:
    client: TestClient = visit_api_context["client"]
    token = _login(client, visit_api_context["doctor_username"], visit_api_context["doctor_password"])
    headers = {"Authorization": f"Bearer {token}"}

    visit_id = _create_visit(client, headers, visit_api_context)

    response = client.put(
        f"/api/v1/visits/{visit_id}/anamnesis",
        headers=headers,
        json={},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_update_diagnoses_creates_audit_event(visit_api_context: Dict[str, object]) -> None:
    client: TestClient = visit_api_context["client"]
    token = _login(client, visit_api_context["doctor_username"], visit_api_context["doctor_password"])
    headers = {"Authorization": f"Bearer {token}"}

    visit_id = _create_visit(client, headers, visit_api_context)

    update_payload = {
        "diagnoses": [
            {"code": "I10", "description": "Hypertensio", "is_primary": True},
            {"code": "R51", "description": "Päänsärky"},
        ]
    }

    response = client.put(
        f"/api/v1/visits/{visit_id}/diagnoses",
        headers=headers,
        json=update_payload,
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert len(body["diagnoses"]) == 2
    assert body["diagnoses"][0]["code"] == "I10"

    with Session(engine) as session:
        events = session.exec(
            select(AuditEvent)
            .where(AuditEvent.action == "visit.update.diagnoses")
            .order_by(AuditEvent.timestamp.desc())
        ).all()

    assert events, "Expected audit event for diagnoses update"
    assert events[0].metadata_json.get("panel") == "diagnoses"
