from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlmodel import Session

from app.db.session import engine, init_db
from app.schemas import ConsentCreate, PatientContactCreate, PatientCreate
from app.services import (
    PatientConflictError,
    PatientMergeError,
    PatientNotFoundError,
    create_patient,
    merge_patients,
)


@pytest.fixture(autouse=True)
def prepare_database() -> None:
    init_db()
    with Session(engine) as session:
        session.exec(text("DELETE FROM patient_history"))
        session.exec(text("DELETE FROM consents"))
        session.exec(text("DELETE FROM patient_contacts"))
        session.exec(text("DELETE FROM patients"))
        session.commit()
    yield


@pytest.fixture
def session() -> Session:
    with Session(engine) as db_session:
        yield db_session


def test_patient_create_accepts_valid_hetu() -> None:
    payload = PatientCreate(
        identifier="131052-308T",
        first_name="Matti",
        last_name="Meikäläinen",
    )
    assert payload.identifier == "131052-308T"


def test_patient_create_rejects_invalid_hetu() -> None:
    with pytest.raises(ValidationError) as exc:
        PatientCreate(
            identifier="131052-308A",
            first_name="Matti",
            last_name="Meikäläinen",
        )

    messages = {error["msg"] for error in exc.value.errors()}
    assert any("tarkistusmerkki" in message for message in messages)


def test_patient_create_requires_demographic_pair_when_identifier_missing() -> None:
    with pytest.raises(ValidationError) as exc:
        PatientCreate(
            first_name="Test",
            last_name="Potilas",
        )

    locations = {error["loc"][0] for error in exc.value.errors()}
    assert {"date_of_birth", "sex"}.issubset(locations)


def test_patient_create_detects_conflicting_identifier(session: Session) -> None:
    data = PatientCreate(
        identifier="131052-308T",
        first_name="Matti",
        last_name="Meikäläinen",
    )
    create_patient(session, data=data, actor_id=1, context={})

    with pytest.raises(PatientConflictError) as exc:
        create_patient(session, data=data, actor_id=2, context={})

    assert exc.value.code == "PATIENT_DUPLICATE"
    assert exc.value.payload.get("matches")
    assert exc.value.payload["matches"][0]["match_type"] == "identifier"


def test_patient_create_detects_conflicting_demographics(session: Session) -> None:
    first = PatientCreate(
        first_name="Maija",
        last_name="Esimerkki",
        date_of_birth=date(1990, 5, 20),
        sex="female",
    )
    duplicate = PatientCreate(
        first_name="Mona",
        last_name="Duplikaatti",
        date_of_birth=date(1990, 5, 20),
        sex="female",
    )

    create_patient(session, data=first, actor_id=1, context={})

    with pytest.raises(PatientConflictError) as exc:
        create_patient(session, data=duplicate, actor_id=2, context={})

    assert exc.value.code == "PATIENT_DUPLICATE"
    assert exc.value.payload["matches"][0]["match_type"] == "demographics"


def test_merge_patients_consolidates_records(session: Session) -> None:
    target = create_patient(
        session,
        data=PatientCreate(
            identifier="131052-308T",
            first_name="Matti",
            last_name="Kohde",
            date_of_birth=date(1952, 10, 13),
            sex="female",
            contacts=[PatientContactCreate(name="Target Contact")],
            consents=[ConsentCreate(type="general", status="granted")],
        ),
        actor_id=1,
        context={},
    )
    source = create_patient(
        session,
        data=PatientCreate(
            first_name="Maija",
            last_name="Lähde",
            date_of_birth=date(1954, 1, 1),
            sex="female",
            contacts=[
                PatientContactCreate(
                    name="Source Contact",
                    phone="0101010",
                )
            ],
            consents=[ConsentCreate(type="research", status="granted")],
        ),
        actor_id=2,
        context={},
    )

    merged = merge_patients(
        session,
        target_patient_id=target.id,
        source_patient_id=source.id,
        actor_id=5,
        context={},
    )

    contact_names = {contact.name for contact in merged.contacts}
    assert contact_names == {"Target Contact", "Source Contact"}

    consent_types = {consent.type for consent in merged.consents}
    assert consent_types == {"general", "research"}

    row = session.exec(
        text("SELECT status, identifier FROM patients WHERE id = :id").bindparams(id=source.id)
    ).one()
    assert row.status == "archived"
    assert row.identifier is None

    change_types = {entry.change_type for entry in merged.history}
    assert "merge" in change_types
    assert "create" in change_types

    # Source history entries are reassigned to the target
    assert any(entry.reason and str(source.id) in entry.reason for entry in merged.history)


def test_merge_patients_rejects_same_source_and_target(session: Session) -> None:
    patient = create_patient(
        session,
        data=PatientCreate(
            identifier="131052-308T",
            first_name="Matti",
            last_name="Sama",
        ),
        actor_id=1,
        context={},
    )

    with pytest.raises(PatientMergeError) as exc:
        merge_patients(
            session,
            target_patient_id=patient.id,
            source_patient_id=patient.id,
            actor_id=1,
            context={},
        )

    assert exc.value.code == "MERGE_SAME_PATIENT"


def test_merge_patients_requires_existing_records(session: Session) -> None:
    patient = create_patient(
        session,
        data=PatientCreate(
            identifier="131052-308T",
            first_name="Matti",
            last_name="Kohde",
        ),
        actor_id=1,
        context={},
    )

    with pytest.raises(PatientNotFoundError):
        merge_patients(
            session,
            target_patient_id=patient.id,
            source_patient_id=999,
            actor_id=1,
            context={},
        )

    with pytest.raises(PatientNotFoundError):
        merge_patients(
            session,
            target_patient_id=999,
            source_patient_id=patient.id,
            actor_id=1,
            context={},
        )
