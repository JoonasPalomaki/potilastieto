from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func
from sqlmodel import Session, select

from app.models import Appointment, AppointmentStatusHistory
from app.schemas.appointment import (
    AppointmentCancelRequest,
    AppointmentCreate,
    AppointmentRead,
    AppointmentStatusRead,
    AppointmentSummary,
    AppointmentUpdate,
)
from app.services import audit


class AppointmentNotFoundError(Exception):
    pass


class AppointmentConflictError(Exception):
    pass


def _build_appointment_read(session: Session, appointment: Appointment) -> AppointmentRead:
    history_entries = session.exec(
        select(AppointmentStatusHistory)
        .where(AppointmentStatusHistory.appointment_id == appointment.id)
        .order_by(AppointmentStatusHistory.changed_at.desc())
    ).all()
    return AppointmentRead(
        id=appointment.id,
        patient_id=appointment.patient_id,
        provider_id=appointment.provider_id,
        service_type=appointment.service_type,
        location=appointment.location,
        start_time=appointment.start_time,
        end_time=appointment.end_time,
        notes=appointment.notes,
        status=appointment.status,
        created_at=appointment.created_at,
        updated_at=appointment.updated_at,
        cancelled_reason=appointment.cancelled_reason,
        cancelled_at=appointment.cancelled_at,
        status_history=[
            AppointmentStatusRead(
                status=entry.status,
                changed_at=entry.changed_at,
                changed_by=entry.changed_by,
                note=entry.note,
            )
            for entry in history_entries
        ],
    )


def _build_summary(appointment: Appointment) -> AppointmentSummary:
    return AppointmentSummary(
        id=appointment.id,
        patient_id=appointment.patient_id,
        provider_id=appointment.provider_id,
        service_type=appointment.service_type,
        start_time=appointment.start_time,
        end_time=appointment.end_time,
        status=appointment.status,
    )


def _add_status_history(
    session: Session,
    appointment_id: int,
    status: str,
    actor_id: Optional[int],
    note: Optional[str] = None,
) -> None:
    entry = AppointmentStatusHistory(
        appointment_id=appointment_id,
        status=status,
        changed_by=actor_id,
        note=note,
        changed_at=datetime.utcnow(),
    )
    session.add(entry)


def _check_overlap(
    session: Session,
    *,
    provider_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_id: Optional[int] = None,
) -> None:
    overlap_stmt = select(Appointment).where(
        Appointment.provider_id == provider_id,
        Appointment.status != "cancelled",
        Appointment.start_time < end_time,
        Appointment.end_time > start_time,
    )
    if exclude_id:
        overlap_stmt = overlap_stmt.where(Appointment.id != exclude_id)
    conflict = session.exec(overlap_stmt).first()
    if conflict:
        raise AppointmentConflictError("PROVIDER_OVERLAP")


def _appointment_list_audit_metadata(
    result: Tuple[List[AppointmentSummary], int], params: Dict[str, object]
) -> Dict[str, object]:
    items, total = result
    metadata: Dict[str, object] = {
        "page": params.get("page", 1),
        "page_size": params.get("page_size", 25),
        "patient_id": params.get("patient_id"),
        "provider_id": params.get("provider_id"),
        "status": params.get("status"),
        "returned": len(items),
        "total": total,
    }
    start_from = params.get("start_from")
    end_to = params.get("end_to")
    if isinstance(start_from, datetime):
        metadata["start_from"] = start_from.isoformat()
    if isinstance(end_to, datetime):
        metadata["end_to"] = end_to.isoformat()
    return {key: value for key, value in metadata.items() if value is not None}


@audit.log_read(
    resource_type="appointment",
    many=True,
    action="appointment.list",
    metadata_getter=_appointment_list_audit_metadata,
)
def list_appointments(
    session: Session,
    *,
    page: int = 1,
    page_size: int = 25,
    patient_id: Optional[int] = None,
    provider_id: Optional[int] = None,
    status: Optional[str] = None,
    start_from: Optional[datetime] = None,
    end_to: Optional[datetime] = None,
) -> Tuple[List[AppointmentSummary], int]:
    statement = select(Appointment)
    count_stmt = select(func.count()).select_from(Appointment)

    filters = []
    if patient_id:
        filters.append(Appointment.patient_id == patient_id)
    if provider_id:
        filters.append(Appointment.provider_id == provider_id)
    if status:
        filters.append(Appointment.status == status)
    if start_from:
        filters.append(Appointment.start_time >= start_from)
    if end_to:
        filters.append(Appointment.end_time <= end_to)

    if filters:
        statement = statement.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

    statement = statement.order_by(Appointment.start_time.desc())
    total = session.exec(count_stmt).one()
    items = session.exec(
        statement.offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [_build_summary(item) for item in items], total


@audit.log_read(resource_type="appointment")
def get_appointment(session: Session, appointment_id: int) -> AppointmentRead:
    appointment = session.get(Appointment, appointment_id)
    if not appointment:
        raise AppointmentNotFoundError
    return _build_appointment_read(session, appointment)


def create_appointment(
    session: Session,
    *,
    data: AppointmentCreate,
    actor_id: Optional[int],
    context: Optional[dict] = None,
) -> AppointmentRead:
    if data.start_time >= data.end_time:
        raise AppointmentConflictError("INVALID_TIME_RANGE")

    _check_overlap(
        session,
        provider_id=data.provider_id,
        start_time=data.start_time,
        end_time=data.end_time,
    )

    appointment = Appointment(
        patient_id=data.patient_id,
        provider_id=data.provider_id,
        service_type=data.service_type,
        location=data.location,
        start_time=data.start_time,
        end_time=data.end_time,
        notes=data.notes,
        status="scheduled",
        created_by=actor_id,
    )
    session.add(appointment)
    session.flush()

    _add_status_history(session, appointment.id, appointment.status, actor_id)

    audit.record_event(
        session,
        actor_id=actor_id,
        action="appointment.create",
        resource_type="appointment",
        resource_id=str(appointment.id),
        metadata={"patient_id": appointment.patient_id},
        context=context or {},
    )

    session.commit()
    session.refresh(appointment)
    return _build_appointment_read(session, appointment)


def update_appointment(
    session: Session,
    *,
    appointment_id: int,
    data: AppointmentUpdate,
    actor_id: Optional[int],
    context: Optional[dict] = None,
) -> AppointmentRead:
    appointment = session.get(Appointment, appointment_id)
    if not appointment:
        raise AppointmentNotFoundError

    new_start = data.start_time or appointment.start_time
    new_end = data.end_time or appointment.end_time
    if new_start >= new_end:
        raise AppointmentConflictError("INVALID_TIME_RANGE")

    _check_overlap(
        session,
        provider_id=data.provider_id or appointment.provider_id,
        start_time=new_start,
        end_time=new_end,
        exclude_id=appointment.id,
    )

    if data.service_type is not None:
        appointment.service_type = data.service_type
    if data.location is not None:
        appointment.location = data.location
    if data.start_time is not None:
        appointment.start_time = data.start_time
    if data.end_time is not None:
        appointment.end_time = data.end_time
    if data.notes is not None:
        appointment.notes = data.notes
    if data.status is not None:
        appointment.status = data.status
        _add_status_history(session, appointment.id, appointment.status, actor_id, data.cancelled_reason)
    if data.cancelled_reason is not None:
        appointment.cancelled_reason = data.cancelled_reason
    appointment.updated_at = datetime.utcnow()

    audit.record_event(
        session,
        actor_id=actor_id,
        action="appointment.update",
        resource_type="appointment",
        resource_id=str(appointment.id),
        metadata={"patient_id": appointment.patient_id},
        context=context or {},
    )

    session.commit()
    session.refresh(appointment)
    return _build_appointment_read(session, appointment)


def cancel_appointment(
    session: Session,
    *,
    appointment_id: int,
    request: AppointmentCancelRequest,
    actor_id: Optional[int],
    context: Optional[dict] = None,
) -> AppointmentRead:
    appointment = session.get(Appointment, appointment_id)
    if not appointment:
        raise AppointmentNotFoundError

    appointment.status = "cancelled"
    appointment.cancelled_reason = request.reason
    appointment.cancelled_at = datetime.utcnow()
    appointment.updated_at = datetime.utcnow()

    _add_status_history(session, appointment.id, appointment.status, actor_id, request.reason)

    audit.record_event(
        session,
        actor_id=actor_id,
        action="appointment.cancel",
        resource_type="appointment",
        resource_id=str(appointment.id),
        metadata={"patient_id": appointment.patient_id, "notify": request.notify_patient},
        context=context or {},
    )

    session.commit()
    session.refresh(appointment)
    return _build_appointment_read(session, appointment)
