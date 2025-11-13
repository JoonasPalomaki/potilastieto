from __future__ import annotations

from datetime import date, datetime
from typing import Dict

import pytest

pytest.importorskip("httpx")

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import settings
from app.db.session import engine, init_db
from app.main import app
from app.models import AuditEvent, Role, User, Visit
from app.schemas import PatientCreate
from app.services import create_patient, ensure_seed_data, security


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    body = response.json()
    return body["access_token"]


@pytest.fixture
def api_test_context() -> Dict[str, object]:
    init_db()
    with Session(engine) as session:
        session.exec(text("DELETE FROM refresh_tokens"))
        session.exec(text("DELETE FROM audit_events"))
        session.exec(text("DELETE FROM lab_results"))
        session.exec(text("DELETE FROM orders"))
        session.exec(text("DELETE FROM clinical_notes"))
        session.exec(text("DELETE FROM visits"))
        session.exec(text("DELETE FROM patient_history"))
        session.exec(text("DELETE FROM consents"))
        session.exec(text("DELETE FROM patient_contacts"))
        session.exec(text("DELETE FROM patients"))
        session.exec(text("DELETE FROM users"))
        session.exec(text("DELETE FROM roles"))
        session.commit()

        ensure_seed_data(session)

        doctor_password = "doctorpass"
        billing_password = "billingpass"
        admin_username = settings.first_superuser
        admin_password = settings.first_superuser_password

        doctor_role = session.exec(select(Role).where(Role.code == "doctor")).one()
        billing_role = session.exec(select(Role).where(Role.code == "billing")).one()

        doctor = User(
            username="doctor",
            password_hash=security.hash_password(doctor_password),
            display_name="Tohtori Testi",
            role_id=doctor_role.id,
        )
        billing = User(
            username="billing",
            password_hash=security.hash_password(billing_password),
            display_name="Laskuttaja Testi",
            role_id=billing_role.id,
        )
        session.add(doctor)
        session.add(billing)
        session.commit()
        session.refresh(doctor)
        session.refresh(billing)

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

        context = {
            "patient_id": patient.id,
            "doctor_username": doctor.username,
            "doctor_password": doctor_password,
            "billing_username": billing.username,
            "billing_password": billing_password,
            "admin_username": admin_username,
            "admin_password": admin_password,
        }

    with TestClient(app) as client:
        context["client"] = client
        yield context


def test_billing_role_can_view_patients(api_test_context: Dict[str, object]) -> None:
    client: TestClient = api_test_context["client"]
    token = _login(client, api_test_context["billing_username"], api_test_context["billing_password"])
    headers = {"Authorization": f"Bearer {token}"}

    list_response = client.get("/api/v1/patients/", headers=headers)
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["items"], "Billing user should see patient summaries"

    detail_response = client.get(
        f"/api/v1/patients/{api_test_context['patient_id']}",
        headers=headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == api_test_context["patient_id"]


def test_patient_detail_returns_visit_summaries(api_test_context: Dict[str, object]) -> None:
    patient_id = api_test_context["patient_id"]
    visit_specs = [
        ("triage", datetime(2024, 4, 30, 8, 30)),
        ("intake", datetime(2024, 5, 2, 9, 0)),
        ("checkup", datetime(2024, 5, 3, 11, 0)),
        ("follow_up", datetime(2024, 5, 4, 10, 0)),
    ]

    with Session(engine) as session:
        for label, start_time in visit_specs:
            session.add(
                Visit(
                    patient_id=patient_id,
                    visit_type="outpatient",
                    reason=f"{label} reason",
                    status="completed",
                    location="Room 1",
                    started_at=start_time,
                    ended_at=start_time,
                )
            )
        session.commit()

    client: TestClient = api_test_context["client"]
    token = _login(client, api_test_context["doctor_username"], api_test_context["doctor_password"])
    headers = {"Authorization": f"Bearer {token}"}

    detail_response = client.get(
        f"/api/v1/patients/{patient_id}",
        headers=headers,
    )

    assert detail_response.status_code == 200
    payload = detail_response.json()
    assert payload["visit_count"] == len(visit_specs)
    assert len(payload["visits"]) == len(visit_specs)

    reasons = [visit["reason"] for visit in payload["visits"][:3]]
    assert reasons == ["follow_up reason", "checkup reason", "intake reason"]


def test_patient_list_audit_metadata(api_test_context: Dict[str, object]) -> None:
    client: TestClient = api_test_context["client"]
    token = _login(client, api_test_context["doctor_username"], api_test_context["doctor_password"])
    headers = {"Authorization": f"Bearer {token}"}
    params = {"page": 1, "page_size": 10, "search": "Test", "status_filter": "active"}

    response = client.get("/api/v1/patients/", headers=headers, params=params)
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"], "Expected patient list to return at least one item"

    with Session(engine) as session:
        events = session.exec(
            select(AuditEvent)
            .where(AuditEvent.action == "patient.list")
            .order_by(AuditEvent.timestamp.desc())
        ).all()

    assert events, "Expected audit events for patient list action"
    assert len(events) == len(payload["items"])

    for event in events:
        metadata = event.metadata_json
        assert metadata.get("returned") == len(payload["items"])
        assert metadata.get("total") == payload["total"]
        assert metadata.get("search") == params["search"]
        assert metadata.get("status") == params["status_filter"]
        assert metadata.get("page") == params["page"]
        assert metadata.get("page_size") == params["page_size"]


def test_billing_role_cannot_modify_patients(api_test_context: Dict[str, object]) -> None:
    client: TestClient = api_test_context["client"]
    token = _login(client, api_test_context["billing_username"], api_test_context["billing_password"])
    headers = {"Authorization": f"Bearer {token}"}

    create_payload = {
        "identifier": "010101-123N",
        "first_name": "Uusi",
        "last_name": "Potilas",
    }

    post_response = client.post("/api/v1/patients/", json=create_payload, headers=headers)
    assert post_response.status_code == 403

    full_payload = {
        "identifier": "010101-123N",
        "first_name": "Uusi",
        "last_name": "Potilas",
        "date_of_birth": "1952-10-13",
        "sex": "female",
    }

    put_response = client.put(
        f"/api/v1/patients/{api_test_context['patient_id']}",
        json=full_payload,
        headers=headers,
    )
    assert put_response.status_code == 403

    patch_response = client.patch(
        f"/api/v1/patients/{api_test_context['patient_id']}",
        json={"last_name": "Muokattu"},
        headers=headers,
    )
    assert patch_response.status_code == 403

    delete_response = client.delete(
        f"/api/v1/patients/{api_test_context['patient_id']}",
        headers=headers,
    )
    assert delete_response.status_code == 403


def test_admin_must_provide_reason_when_archiving(api_test_context: Dict[str, object]) -> None:
    client: TestClient = api_test_context["client"]
    token = _login(client, api_test_context["admin_username"], api_test_context["admin_password"])
    headers = {"Authorization": f"Bearer {token}"}

    response = client.delete(
        f"/api/v1/patients/{api_test_context['patient_id']}",
        headers=headers,
    )

    assert response.status_code == 422


def test_archived_patients_are_read_only_and_restore_logs_reason(api_test_context: Dict[str, object]) -> None:
    client: TestClient = api_test_context["client"]
    admin_headers = {
        "Authorization": f"Bearer {_login(client, api_test_context['admin_username'], api_test_context['admin_password'])}"
    }
    archive_reason = "Tietopyyntö asiakkaalta"

    delete_response = client.delete(
        f"/api/v1/patients/{api_test_context['patient_id']}",
        json={"reason": archive_reason},
        headers=admin_headers,
    )
    assert delete_response.status_code == 204

    doctor_headers = {
        "Authorization": f"Bearer {_login(client, api_test_context['doctor_username'], api_test_context['doctor_password'])}"
    }
    patch_response = client.patch(
        f"/api/v1/patients/{api_test_context['patient_id']}",
        json={"last_name": "Muokattu"},
        headers=doctor_headers,
    )
    assert patch_response.status_code == 409
    payload = patch_response.json()
    assert payload.get("code") == "PATIENT_ARCHIVED"

    restore_reason = "Arkistointi peruttu"  # restore reason
    restore_response = client.post(
        f"/api/v1/patients/{api_test_context['patient_id']}/restore",
        json={"reason": restore_reason},
        headers=admin_headers,
    )
    assert restore_response.status_code == 200
    restored = restore_response.json()
    assert restored["status"] == "active"
    assert restored["archived_at"] is None

    history_entries = restored["history"]
    history_reasons = {(entry["change_type"], entry.get("reason")) for entry in history_entries}
    assert ("archive", archive_reason) in history_reasons
    assert ("restore", restore_reason) in history_reasons

    with Session(engine) as session:
        events = session.exec(
            select(AuditEvent)
            .where(
                AuditEvent.resource_type == "patient",
                AuditEvent.resource_id == str(api_test_context["patient_id"]),
                AuditEvent.action.in_(["patient.archive", "patient.restore"]),
            )
        ).all()

    recorded_reasons = {event.metadata_json.get("reason") for event in events}
    assert {archive_reason, restore_reason}.issubset(recorded_reasons)
