from __future__ import annotations

from datetime import date, datetime
from typing import Dict

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.models import AuditEvent, Patient, PatientHistory
from app.models.visit import Visit
from app.schemas import ConsentCreate, PatientContactCreate, PatientCreate, PatientUpdate
from app.services import (
    PatientConflictError,
    PatientArchivedError,
    PatientIdentifierLockedError,
    PatientMergeError,
    PatientNotArchivedError,
    PatientNotFoundError,
    archive_patient,
    create_patient,
    get_patient,
    patch_patient,
    merge_patients,
    restore_patient,
    update_patient,
)


@pytest.fixture(autouse=True)
def prepare_database() -> None:
    init_db()
    with Session(engine) as session:
        session.exec(text("DELETE FROM audit_events"))
        session.exec(text("DELETE FROM lab_results"))
        session.exec(text("DELETE FROM orders"))
        session.exec(text("DELETE FROM clinical_notes"))
        session.exec(text("DELETE FROM visits"))
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


def test_update_patient_blocks_identifier_change_with_dependents(session: Session) -> None:
    patient = create_patient(
        session,
        data=PatientCreate(
            identifier="131052-308T",
            first_name="Test",
            last_name="Potilas",
            date_of_birth=date(1952, 10, 13),
            sex="female",
        ),
        actor_id=None,
        context={},
    )

    session.add(Visit(patient_id=patient.id))
    session.commit()

    update_payload = PatientCreate(
        identifier="131052-302L",
        first_name="Test",
        last_name="Potilas",
        date_of_birth=patient.date_of_birth,
        sex=patient.sex,
    )

    with pytest.raises(PatientIdentifierLockedError) as exc:
        update_patient(
            session,
            patient_id=patient.id,
            data=update_payload,
            actor_id=None,
            actor_role="doctor",
            reason="Päivitys",
            context={},
        )

    assert exc.value.code == "IDENTIFIER_LOCKED"
    session.rollback()

    result = update_patient(
        session,
        patient_id=patient.id,
        data=update_payload,
        actor_id=None,
        actor_role="admin",
        reason="Ylläpidon muutos",
        context={},
    )

    assert result.identifier == "131052-302L"


def test_patch_patient_blocks_identifier_change_with_dependents(session: Session) -> None:
    patient = create_patient(
        session,
        data=PatientCreate(
            identifier="131052-308T",
            first_name="Test",
            last_name="Potilas",
            date_of_birth=date(1952, 10, 13),
            sex="female",
        ),
        actor_id=None,
        context={},
    )

    session.add(Visit(patient_id=patient.id))
    session.commit()

    patch_payload = PatientUpdate(
        identifier="131052-302L",
        first_name="Test",
        last_name="Potilas",
    )

    with pytest.raises(PatientIdentifierLockedError):
        patch_patient(
            session,
            patient_id=patient.id,
            data=patch_payload,
            actor_id=None,
            actor_role="doctor",
            context={},
        )

    session.rollback()

    patched = patch_patient(
        session,
        patient_id=patient.id,
        data=patch_payload,
        actor_id=None,
        actor_role="admin",
        context={},
    )

    assert patched.identifier == "131052-302L"


def test_update_patient_rejects_archived_records(session: Session) -> None:
    patient = create_patient(
        session,
        data=PatientCreate(
            identifier="131052-308T",
            first_name="Arkistoitu",
            last_name="Potilas",
        ),
        actor_id=1,
        context={},
    )

    archive_patient(
        session,
        patient_id=patient.id,
        actor_id=1,
        reason="Arkistointi testia varten",
        context={},
    )

    with pytest.raises(PatientArchivedError):
        update_patient(
            session,
            patient_id=patient.id,
            data=PatientCreate(
                identifier="131052-308T",
                first_name="Muokattu",
                last_name="Potilas",
            ),
            actor_id=2,
            actor_role="admin",
            reason="Yritetty muokkaus",
            context={},
        )


def test_patch_patient_rejects_archived_records(session: Session) -> None:
    patient = create_patient(
        session,
        data=PatientCreate(
            identifier="131052-309U",
            first_name="Arkisto",
            last_name="Muokkaus",
        ),
        actor_id=1,
        context={},
    )

    archive_patient(
        session,
        patient_id=patient.id,
        actor_id=1,
        reason="Arkistointi ennen korjausta",
        context={},
    )

    with pytest.raises(PatientArchivedError):
        patch_patient(
            session,
            patient_id=patient.id,
            data=PatientUpdate(first_name="Arkisto", last_name="Uusi"),
            actor_id=2,
            actor_role="admin",
            context={},
        )


def test_restore_patient_reactivates_and_logs_reason(session: Session) -> None:
    patient = create_patient(
        session,
        data=PatientCreate(
            first_name="Palautus",
            last_name="Testi",
            date_of_birth=date(1980, 1, 1),
            sex="female",
        ),
        actor_id=1,
        context={},
    )

    archive_reason = "Asiakas poistui"
    restore_reason = "Palautettu pyynnöstä"

    archive_patient(
        session,
        patient_id=patient.id,
        actor_id=1,
        reason=archive_reason,
        context={},
    )

    restored = restore_patient(
        session,
        patient_id=patient.id,
        actor_id=2,
        reason=restore_reason,
        context={},
    )

    assert restored.status == "active"
    assert restored.archived_at is None

    history_rows = session.exec(
        select(PatientHistory).where(PatientHistory.patient_id == patient.id).order_by(PatientHistory.changed_at)
    ).all()
    reasons = [(row.change_type, row.reason) for row in history_rows]
    assert ("archive", archive_reason) in reasons
    assert ("restore", restore_reason) in reasons

    events = session.exec(
        select(AuditEvent).where(
            AuditEvent.resource_type == "patient",
            AuditEvent.resource_id == str(patient.id),
            AuditEvent.action.in_(["patient.archive", "patient.restore"]),
        )
    ).all()
    recorded_reasons = {event.metadata_json.get("reason") for event in events}
    assert {archive_reason, restore_reason}.issubset(recorded_reasons)

    patient_row = session.get(Patient, patient.id)
    assert patient_row is not None
    assert patient_row.status == "active"


def test_get_patient_includes_sorted_visit_summaries(session: Session) -> None:
    created_patient = create_patient(
        session,
        data=PatientCreate(
            identifier="131052-308T",
            first_name="Visit",
            last_name="Tester",
        ),
        actor_id=1,
        context={},
    )

    visit_specs = [
        ("triage", datetime(2024, 4, 30, 8, 30)),
        ("intake", datetime(2024, 5, 2, 9, 0)),
        ("checkup", datetime(2024, 5, 3, 11, 0)),
        ("follow_up", datetime(2024, 5, 4, 10, 0)),
    ]

    labels_by_id: Dict[int, str] = {}
    for label, start_time in visit_specs:
        visit = Visit(
            patient_id=created_patient.id,
            visit_type="outpatient",
            reason=f"{label} reason",
            status="completed",
            location="Room 1",
            started_at=start_time,
            ended_at=start_time,
        )
        session.add(visit)
        session.flush()
        labels_by_id[visit.id] = label

    session.commit()

    patient_read = get_patient(session, created_patient.id)

    assert patient_read.visit_count == len(visit_specs)
    assert len(patient_read.visits) == len(visit_specs)

    ordered_labels = [labels_by_id[visit.id] for visit in patient_read.visits[:3]]
    assert ordered_labels == ["follow_up", "checkup", "intake"]
