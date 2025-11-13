from __future__ import annotations

from typing import Dict

import pytest

pytest.importorskip("httpx")

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import settings
from app.db.session import engine, init_db
from app.main import app
from app.models import AuditEvent, DiagnosisCode, Role, User
from app.services import ensure_seed_data, security


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def diagnosis_api_context() -> Dict[str, object]:
    init_db()
    with Session(engine) as session:
        session.exec(text("DELETE FROM refresh_tokens"))
        session.exec(text("DELETE FROM audit_events"))
        session.exec(text("DELETE FROM diagnosis_codes"))
        session.exec(text("DELETE FROM users"))
        session.exec(text("DELETE FROM roles"))
        session.commit()

        ensure_seed_data(session)

        doctor_password = "doctorpass"
        doctor_role = session.exec(select(Role).where(Role.code == "doctor")).one()
        doctor = User(
            username="doctor.diagnosis",
            password_hash=security.hash_password(doctor_password),
            display_name="Doctor Diagnosis",
            role_id=doctor_role.id,
        )
        session.add(doctor)
        session.commit()
        session.refresh(doctor)

        context: Dict[str, object] = {
            "doctor_username": doctor.username,
            "doctor_password": doctor_password,
            "admin_username": settings.first_superuser,
            "admin_password": settings.first_superuser_password,
        }

    with TestClient(app) as client:
        context["client"] = client
        yield context


def test_admin_can_import_codes(diagnosis_api_context: Dict[str, object]) -> None:
    client: TestClient = diagnosis_api_context["client"]
    token = _login(
        client,
        diagnosis_api_context["admin_username"],
        diagnosis_api_context["admin_password"],
    )
    headers = {"Authorization": f"Bearer {token}"}
    csv_payload = """code,short_description,long_description,is_deleted\nA10.1,Alpha,,false\nB20.1,Beta,,true\n"""

    response = client.post(
        "/api/v1/diagnosis-codes/import",
        files={"csv_file": ("codes.csv", csv_payload, "text/csv")},
        headers=headers,
    )
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["inserted"] == 2
    assert summary["marked_deleted"] == 1

    with Session(engine) as session:
        codes = session.exec(select(DiagnosisCode)).all()
        assert len(codes) == 2
        deleted = [code for code in codes if code.is_deleted]
        assert len(deleted) == 1
        events = session.exec(
            select(AuditEvent).where(AuditEvent.action == "diagnosis_code.import")
        ).all()
        assert events
        metadata = events[0].metadata_json
        assert metadata.get("inserted") == 2
        assert metadata.get("filename") == "codes.csv"


def test_doctor_cannot_import_codes(diagnosis_api_context: Dict[str, object]) -> None:
    client: TestClient = diagnosis_api_context["client"]
    token = _login(
        client,
        diagnosis_api_context["doctor_username"],
        diagnosis_api_context["doctor_password"],
    )
    headers = {"Authorization": f"Bearer {token}"}
    csv_payload = "code,short_description,long_description,is_deleted\nA10.1,Alpha,,false\n"

    response = client.post(
        "/api/v1/diagnosis-codes/import",
        files={"csv_file": ("codes.csv", csv_payload, "text/csv")},
        headers=headers,
    )
    assert response.status_code == 403


def test_search_endpoint_supports_pagination_and_deleted_filter(
    diagnosis_api_context: Dict[str, object]
) -> None:
    client: TestClient = diagnosis_api_context["client"]
    admin_token = _login(
        client,
        diagnosis_api_context["admin_username"],
        diagnosis_api_context["admin_password"],
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    csv_payload = """code,short_description,long_description,is_deleted\nA10.1,Alpha,,false\nB20.1,Beta,,true\nC30,Charlie,,false\n"""
    client.post(
        "/api/v1/diagnosis-codes/import",
        files={"csv_file": ("codes.csv", csv_payload, "text/csv")},
        headers=admin_headers,
    )

    doctor_token = _login(
        client,
        diagnosis_api_context["doctor_username"],
        diagnosis_api_context["doctor_password"],
    )
    doctor_headers = {"Authorization": f"Bearer {doctor_token}"}

    list_response = client.get(
        "/api/v1/diagnosis-codes/",
        headers=doctor_headers,
        params={"page": 1, "page_size": 1},
    )
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 1

    include_deleted = client.get(
        "/api/v1/diagnosis-codes/",
        headers=doctor_headers,
        params={"search": "B20", "include_deleted": True},
    )
    assert include_deleted.status_code == 200
    include_payload = include_deleted.json()
    assert include_payload["total"] == 1
    assert include_payload["items"][0]["is_deleted"] is True

    default_deleted = client.get(
        "/api/v1/diagnosis-codes/",
        headers=doctor_headers,
        params={"search": "B20"},
    )
    assert default_deleted.status_code == 200
    assert default_deleted.json()["total"] == 0
