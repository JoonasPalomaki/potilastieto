from __future__ import annotations

from io import StringIO

import pytest
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import settings
from app.db.session import engine, init_db
from app.models import DiagnosisCode, User
from app.services import ensure_seed_data
from app.services.diagnosis_codes import (
    DiagnosisCodeImportResult,
    import_diagnosis_codes,
    search_diagnosis_codes,
)


@pytest.fixture(autouse=True)
def clean_database() -> None:
    init_db()
    with Session(engine) as session:
        session.exec(text("DELETE FROM audit_events"))
        session.exec(text("DELETE FROM diagnosis_codes"))
        session.exec(text("DELETE FROM users"))
        session.exec(text("DELETE FROM roles"))
        session.commit()


@pytest.fixture
def session() -> Session:
    with Session(engine) as db_session:
        ensure_seed_data(db_session)
        yield db_session


@pytest.fixture
def admin_user(session: Session) -> User:
    return session.exec(
        select(User).where(User.username == settings.first_superuser)
    ).one()


def _import_from_string(
    session: Session,
    admin_user: User,
    payload: str,
) -> DiagnosisCodeImportResult:
    return import_diagnosis_codes(
        session,
        csv_stream=StringIO(payload),
        actor_id=admin_user.id,
        context={"request_id": "svc-test"},
        filename="test.csv",
    )


def test_import_creates_and_updates_codes(session: Session, admin_user: User) -> None:
    csv_payload = """code,short_description,long_description,is_deleted\nA10.1,Flu,Seasonal flu,false\nB20,Other,Other desc,true\n"""
    summary = _import_from_string(session, admin_user, csv_payload)

    assert summary.total_rows == 2
    assert summary.inserted == 2
    assert summary.marked_deleted == 1
    assert not summary.errors

    updated_payload = """code,short_description,long_description,is_deleted\nA10.1,Updated,Updated desc,false\nB20,Other,Other desc,true\n"""
    second_summary = _import_from_string(session, admin_user, updated_payload)
    assert second_summary.updated == 1
    assert second_summary.inserted == 0

    records = session.exec(
        select(DiagnosisCode).order_by(DiagnosisCode.code)
    ).all()
    assert len(records) == 2
    assert records[0].short_description == "Updated"
    assert records[1].is_deleted is True


def test_import_handles_validation_errors(session: Session, admin_user: User) -> None:
    csv_payload = """code,short_description,long_description,is_deleted\n,Missing,,false\nC30,Valid,,yes\n"""
    summary = _import_from_string(session, admin_user, csv_payload)

    assert summary.skipped == 1
    assert len(summary.errors) == 1

    valid = session.exec(select(DiagnosisCode)).all()
    assert len(valid) == 1
    assert valid[0].is_deleted is True


def test_import_requires_all_headers(session: Session, admin_user: User) -> None:
    bad_payload = "code,short_description,is_deleted\nA10,Test,false\n"
    with pytest.raises(ValueError):
        _import_from_string(session, admin_user, bad_payload)


def test_search_filters_and_paginates(session: Session, admin_user: User) -> None:
    csv_payload = """code,short_description,long_description,is_deleted\nA10.1,Alpha,,false\nB20.1,Beta,,true\nC30,Charlie,,false\n"""
    _import_from_string(session, admin_user, csv_payload)

    items, total = search_diagnosis_codes(
        session,
        search="A10",
        include_deleted=False,
        page=1,
        page_size=10,
    )
    assert total == 1
    assert len(items) == 1
    assert items[0].code == "A10.1"

    page_items, page_total = search_diagnosis_codes(
        session,
        include_deleted=False,
        page=1,
        page_size=1,
    )
    assert page_total == 2
    assert len(page_items) == 1

    include_deleted_items, include_deleted_total = search_diagnosis_codes(
        session,
        search="b20.1",
        include_deleted=True,
        page=1,
        page_size=10,
    )
    assert include_deleted_total == 1
    assert include_deleted_items[0].is_deleted is True
