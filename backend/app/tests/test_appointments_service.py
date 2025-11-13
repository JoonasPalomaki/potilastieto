from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

import pytest
from sqlalchemy import text
from sqlmodel import Session

from app.db.session import engine, init_db
from app.schemas import (
    AppointmentCancelRequest,
    AppointmentCreate,
    AppointmentRescheduleRequest,
    PatientCreate,
)
from app.services import (
    AppointmentConflictError,
    cancel_appointment,
    create_appointment,
    create_patient,
    reschedule_appointment,
    search_availability,
)
from app.services.notifications import (
    NotificationBackend,
    NotificationMessage,
    reset_notification_backend,
    set_notification_backend,
)


class RecordingBackend(NotificationBackend):
    def __init__(self) -> None:
        self.sent: List[NotificationMessage] = []

    def send_email(self, *, to: str, subject: str, body: str) -> NotificationMessage:  # type: ignore[override]
        message = super().send_email(to=to, subject=subject, body=body)
        self.sent.append(message)
        return message

    def send_sms(self, *, to: str, body: str) -> NotificationMessage:  # type: ignore[override]
        message = super().send_sms(to=to, body=body)
        self.sent.append(message)
        return message


@pytest.fixture(autouse=True)
def prepare_database() -> None:
    init_db()
    with Session(engine) as session:
        session.exec(text("DELETE FROM appointment_status_history"))
        session.exec(text("DELETE FROM appointments"))
        session.exec(text("DELETE FROM audit_events"))
        session.exec(text("DELETE FROM diagnosis_codes"))
        session.exec(text("DELETE FROM patient_contacts"))
        session.exec(text("DELETE FROM consents"))
        session.exec(text("DELETE FROM patients"))
        session.commit()
    yield


@pytest.fixture
def session() -> Session:
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture
def notification_backend() -> RecordingBackend:
    backend = RecordingBackend()
    set_notification_backend(backend)
    yield backend
    reset_notification_backend()


def _create_patient(session: Session) -> int:
    patient = create_patient(
        session,
        data=PatientCreate(
            identifier="131052-308T",
            first_name="Matti",
            last_name="Meikäläinen",
            contact_info={"email": "matti@example.com", "phone": "+358401234567"},
        ),
        actor_id=None,
        context={},
    )
    return patient.id


def test_search_availability_returns_free_slots(session: Session, notification_backend: RecordingBackend) -> None:
    patient_id = _create_patient(session)
    provider_id = 10
    start = datetime(2024, 1, 1, 9, 0)
    create_appointment(
        session,
        data=AppointmentCreate(
            patient_id=patient_id,
            provider_id=provider_id,
            service_type="consultation",
            location="Room 1",
            start_time=start,
            end_time=start + timedelta(minutes=30),
        ),
        actor_id=None,
        context={},
    )

    availability = search_availability(
        session,
        start_from=start,
        end_to=start + timedelta(hours=3),
        provider_ids=[provider_id],
        location="Room 1",
        slot_minutes=30,
    )

    assert availability
    room_availability = availability[0]
    slot_starts = {slot.start_time for slot in room_availability.slots}
    assert start not in slot_starts
    assert start + timedelta(minutes=30) in slot_starts


def test_reschedule_records_history_and_notifies(session: Session, notification_backend: RecordingBackend) -> None:
    patient_id = _create_patient(session)
    provider_id = 15
    original_start = datetime(2024, 1, 2, 8, 0)
    appointment = create_appointment(
        session,
        data=AppointmentCreate(
            patient_id=patient_id,
            provider_id=provider_id,
            location="Room 5",
            start_time=original_start,
            end_time=original_start + timedelta(minutes=30),
        ),
        actor_id=1,
        context={},
    )

    baseline_notifications = len(notification_backend.sent)

    updated = reschedule_appointment(
        session,
        appointment_id=appointment.id,
        data=AppointmentRescheduleRequest(
            start_time=original_start + timedelta(hours=1),
            end_time=original_start + timedelta(hours=1, minutes=30),
            reason="Patient requested later time",
        ),
        actor_id=1,
        context={},
    )

    assert updated.start_time == original_start + timedelta(hours=1)
    assert updated.status_history
    latest_entry = updated.status_history[0]
    assert latest_entry.status == "rescheduled"
    assert "from=" in (latest_entry.note or "")
    assert "reason=Patient requested later time" in (latest_entry.note or "")

    assert len(notification_backend.sent) > baseline_notifications


def test_reschedule_conflict_returns_alternatives(session: Session, notification_backend: RecordingBackend) -> None:
    patient_id = _create_patient(session)
    provider_id = 25
    base_start = datetime(2024, 1, 3, 9, 0)
    appointment = create_appointment(
        session,
        data=AppointmentCreate(
            patient_id=patient_id,
            provider_id=provider_id,
            location="Room 2",
            start_time=base_start,
            end_time=base_start + timedelta(minutes=30),
        ),
        actor_id=None,
        context={},
    )

    # Occupy the desired reschedule slot
    create_appointment(
        session,
        data=AppointmentCreate(
            patient_id=patient_id,
            provider_id=provider_id,
            location="Room 2",
            start_time=base_start + timedelta(hours=1),
            end_time=base_start + timedelta(hours=1, minutes=30),
        ),
        actor_id=None,
        context={},
    )

    with pytest.raises(AppointmentConflictError) as exc:
        reschedule_appointment(
            session,
            appointment_id=appointment.id,
            data=AppointmentRescheduleRequest(
                start_time=base_start + timedelta(hours=1),
                end_time=base_start + timedelta(hours=1, minutes=30),
                reason="Slot requested",
            ),
            actor_id=None,
            context={},
        )

    assert exc.value.alternatives
    assert all(slot.start_time != base_start + timedelta(hours=1) for slot in exc.value.alternatives)


def test_cancel_notification_respects_flag(session: Session, notification_backend: RecordingBackend) -> None:
    patient_id = _create_patient(session)
    provider_id = 33
    start = datetime(2024, 1, 4, 10, 0)
    appointment = create_appointment(
        session,
        data=AppointmentCreate(
            patient_id=patient_id,
            provider_id=provider_id,
            location="Room 4",
            start_time=start,
            end_time=start + timedelta(minutes=30),
        ),
        actor_id=None,
        context={},
    )

    baseline_notifications = len(notification_backend.sent)

    cancel_appointment(
        session,
        appointment_id=appointment.id,
        request=AppointmentCancelRequest(reason="Cancelled", notify_patient=False),
        actor_id=None,
        context={},
    )

    assert len(notification_backend.sent) == baseline_notifications

    new_appointment = create_appointment(
        session,
        data=AppointmentCreate(
            patient_id=patient_id,
            provider_id=provider_id,
            location="Room 4",
            start_time=start + timedelta(days=1),
            end_time=start + timedelta(days=1, minutes=30),
        ),
        actor_id=None,
        context={},
    )

    cancel_appointment(
        session,
        appointment_id=new_appointment.id,
        request=AppointmentCancelRequest(reason="Cancelled", notify_patient=True),
        actor_id=None,
        context={},
    )

    assert len(notification_backend.sent) > baseline_notifications
