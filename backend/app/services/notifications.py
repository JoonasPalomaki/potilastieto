from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlmodel import Session

from app.models import Appointment, Patient


@dataclass
class NotificationMessage:
    channel: str
    recipient: str
    subject: Optional[str] = None
    body: str = ""


class NotificationBackend:
    """Very small stub backend that records the outgoing payload."""

    def send_email(self, *, to: str, subject: str, body: str) -> NotificationMessage:
        return NotificationMessage(channel="email", recipient=to, subject=subject, body=body)

    def send_sms(self, *, to: str, body: str) -> NotificationMessage:
        return NotificationMessage(channel="sms", recipient=to, body=body)


_backend: NotificationBackend = NotificationBackend()


def get_notification_backend() -> NotificationBackend:
    return _backend


def set_notification_backend(backend: NotificationBackend) -> None:
    global _backend
    _backend = backend


def reset_notification_backend() -> None:
    set_notification_backend(NotificationBackend())


def _collect_patient(session: Session, patient_id: int) -> Optional[Patient]:
    patient = session.get(Patient, patient_id)
    return patient


def _extract_contact_value(contact_info: dict, key: str) -> Optional[str]:
    raw_value = contact_info.get(key) if isinstance(contact_info, dict) else None
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        return stripped or None
    return None


def _patient_display_name(patient: Patient) -> str:
    first = (patient.first_name or "").strip()
    last = (patient.last_name or "").strip()
    name = f"{first} {last}".strip()
    return name or "Potilas"


def _compose_time_range(appointment: Appointment) -> str:
    start = appointment.start_time.isoformat()
    end = appointment.end_time.isoformat()
    return f"{start} – {end}"


def _send_for_patient(
    *,
    session: Session,
    appointment: Appointment,
    subject: str,
    email_body: str,
    sms_body: str,
    skip_if_missing: bool = True,
) -> List[NotificationMessage]:
    patient = _collect_patient(session, appointment.patient_id)
    if patient is None:
        return []

    contact_info = patient.contact_info or {}
    email = _extract_contact_value(contact_info, "email")
    phone = _extract_contact_value(contact_info, "phone")

    if skip_if_missing and not any([email, phone]):
        return []

    backend = get_notification_backend()
    messages: List[NotificationMessage] = []

    if email:
        messages.append(backend.send_email(to=email, subject=subject, body=email_body))
    if phone:
        messages.append(backend.send_sms(to=phone, body=sms_body))

    return messages


def notify_appointment_created(session: Session, appointment: Appointment) -> List[NotificationMessage]:
    name = _patient_display_name(session.get(Patient, appointment.patient_id)) if appointment.patient_id else "Potilas"
    time_range = _compose_time_range(appointment)
    subject = "Ajanvaraus vahvistettu"
    email_body = (
        f"Hei {name},\n\n"
        f"Aikasi on varattu ajalle {time_range}. Vastaanotto: {appointment.location or 'ei määritelty'}."
    )
    sms_body = f"Aikasi {time_range}. Huone: {appointment.location or '-'}"
    return _send_for_patient(
        session=session,
        appointment=appointment,
        subject=subject,
        email_body=email_body,
        sms_body=sms_body,
    )


def notify_appointment_rescheduled(
    session: Session,
    appointment: Appointment,
    *,
    previous_start: str,
    previous_end: str,
    reason: Optional[str] = None,
) -> List[NotificationMessage]:
    patient = session.get(Patient, appointment.patient_id)
    name = _patient_display_name(patient) if patient else "Potilas"
    time_range = _compose_time_range(appointment)
    subject = "Aika muutettu"
    email_body = (
        f"Hei {name},\n\n"
        f"Aikasi on siirretty ajasta {previous_start} – {previous_end} ajalle {time_range}."
    )
    if reason:
        email_body += f"\nSyy: {reason}"
    sms_body = f"Aikasi siirretty ajalle {time_range}"
    if reason:
        sms_body += f" ({reason})"
    return _send_for_patient(
        session=session,
        appointment=appointment,
        subject=subject,
        email_body=email_body,
        sms_body=sms_body,
    )


def notify_appointment_cancelled(
    session: Session,
    appointment: Appointment,
    *,
    reason: Optional[str],
) -> List[NotificationMessage]:
    patient = session.get(Patient, appointment.patient_id)
    name = _patient_display_name(patient) if patient else "Potilas"
    time_range = _compose_time_range(appointment)
    subject = "Aika peruttu"
    email_body = f"Hei {name},\n\nAikasi {time_range} on peruttu."
    if reason:
        email_body += f"\nSyy: {reason}"
    sms_body = f"Aikasi {time_range} on peruttu"
    if reason:
        sms_body += f" ({reason})"
    return _send_for_patient(
        session=session,
        appointment=appointment,
        subject=subject,
        email_body=email_body,
        sms_body=sms_body,
        skip_if_missing=False,
    )
