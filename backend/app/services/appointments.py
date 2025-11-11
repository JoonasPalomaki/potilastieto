from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import and_, func
from sqlmodel import Session, select

from app.models import Appointment, AppointmentStatusHistory
from app.schemas.appointment import (
    AppointmentCancelRequest,
    AppointmentCreate,
    AppointmentAvailability,
    AppointmentRead,
    AppointmentRescheduleRequest,
    AppointmentStatusRead,
    AppointmentSummary,
    AppointmentUpdate,
    AvailabilitySlot,
)
from app.services import audit
from app.services.audit_policy import ensure_appointment_metadata, make_patient_reference
from app.services.notifications import (
    notify_appointment_cancelled,
    notify_appointment_created,
    notify_appointment_rescheduled,
)


class AppointmentNotFoundError(Exception):
    pass


class AppointmentConflictError(Exception):
    def __init__(
        self,
        code: str,
        *,
        message: Optional[str] = None,
        alternatives: Optional[List[AvailabilitySlot]] = None,
    ) -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code
        self.alternatives = alternatives or []


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
        "provider_id": params.get("provider_id"),
        "status": params.get("status"),
        "returned": len(items),
        "total": total,
    }
    patient_id = params.get("patient_id")
    if patient_id is not None:
        metadata["patient_ref"] = make_patient_reference(int(patient_id))
    start_from = params.get("start_from")
    end_to = params.get("end_to")
    if isinstance(start_from, datetime):
        metadata["start_from"] = start_from.isoformat()
    if isinstance(end_to, datetime):
        metadata["end_to"] = end_to.isoformat()
    return {key: value for key, value in metadata.items() if value is not None}


def _merge_intervals(intervals: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    if not intervals:
        return []
    sorted_intervals = sorted(intervals, key=lambda item: item[0])
    merged: List[Tuple[datetime, datetime]] = [sorted_intervals[0]]
    for current_start, current_end in sorted_intervals[1:]:
        last_start, last_end = merged[-1]
        if current_start <= last_end:
            merged[-1] = (last_start, max(last_end, current_end))
        else:
            merged.append((current_start, current_end))
    return merged


def _chunk_interval(
    start: datetime, end: datetime, slot_minutes: int
) -> List[Tuple[datetime, datetime]]:
    slots: List[Tuple[datetime, datetime]] = []
    step = timedelta(minutes=slot_minutes)
    current = start
    while current + step <= end:
        slots.append((current, current + step))
        current += step
    return slots


def _generate_availability_slots(
    *,
    start_from: datetime,
    end_to: datetime,
    slot_minutes: int,
    busy: List[Tuple[datetime, datetime]],
) -> List[AvailabilitySlot]:
    clamped = [
        (
            max(start_from, interval_start),
            min(end_to, interval_end),
        )
        for interval_start, interval_end in busy
        if interval_start < end_to and interval_end > start_from
    ]
    merged_busy = _merge_intervals(clamped)
    pointer = start_from
    slots: List[AvailabilitySlot] = []
    for busy_start, busy_end in merged_busy:
        if busy_start > pointer:
            free_end = min(busy_start, end_to)
            for chunk_start, chunk_end in _chunk_interval(pointer, free_end, slot_minutes):
                slots.append(AvailabilitySlot(start_time=chunk_start, end_time=chunk_end))
        pointer = max(pointer, busy_end)
        if pointer >= end_to:
            break
    if pointer < end_to:
        for chunk_start, chunk_end in _chunk_interval(pointer, end_to, slot_minutes):
            slots.append(AvailabilitySlot(start_time=chunk_start, end_time=chunk_end))
    return slots


def _availability_audit_metadata(
    result: List[AppointmentAvailability], params: Dict[str, object]
) -> Dict[str, object]:
    slot_count = sum(len(entry.slots) for entry in result)
    metadata: Dict[str, object] = {
        "provider_ids": params.get("provider_ids"),
        "location": params.get("location"),
        "slot_minutes": params.get("slot_minutes"),
        "groups": len(result),
        "slot_count": slot_count,
    }
    return {key: value for key, value in metadata.items() if value not in (None, [], {})}


@audit.log_read(
    resource_type="appointment",
    many=True,
    action="appointment.availability",
    metadata_getter=_availability_audit_metadata,
)
def search_availability(
    session: Session,
    *,
    start_from: datetime,
    end_to: datetime,
    provider_ids: Optional[List[int]] = None,
    location: Optional[str] = None,
    slot_minutes: int = 30,
    exclude_appointment_id: Optional[int] = None,
) -> List[AppointmentAvailability]:
    if start_from >= end_to:
        raise ValueError("start_from must be before end_to")
    if slot_minutes <= 0:
        raise ValueError("slot_minutes must be positive")

    normalized_providers = [pid for pid in (provider_ids or []) if pid is not None]
    if not normalized_providers:
        raise ValueError("At least one provider_id must be supplied")

    statement = select(Appointment).where(
        Appointment.status != "cancelled",
        Appointment.start_time < end_to,
        Appointment.end_time > start_from,
    )

    statement = statement.where(Appointment.provider_id.in_(normalized_providers))

    if location is not None:
        statement = statement.where(Appointment.location == location)
    if exclude_appointment_id is not None:
        statement = statement.where(Appointment.id != exclude_appointment_id)

    rows = session.exec(statement).all()

    grouped: Dict[Tuple[int, Optional[str]], List[Tuple[datetime, datetime]]] = {}
    for row in rows:
        key = (row.provider_id, row.location)
        grouped.setdefault(key, []).append((row.start_time, row.end_time))

    keys: Set[Tuple[int, Optional[str]]] = set(grouped.keys())
    if location is not None:
        for provider_id in normalized_providers:
            keys.add((provider_id, location))
    else:
        for provider_id in normalized_providers:
            has_key = any(existing[0] == provider_id for existing in keys)
            if not has_key:
                keys.add((provider_id, None))

    availability: List[AppointmentAvailability] = []
    for provider_id, provider_location in sorted(keys, key=lambda item: (item[0], item[1] or "")):
        if provider_location is None:
            busy_intervals: List[Tuple[datetime, datetime]] = []
            for existing_key, intervals in grouped.items():
                if existing_key[0] == provider_id:
                    busy_intervals.extend(intervals)
        else:
            busy_intervals = grouped.get((provider_id, provider_location), [])
        slots = _generate_availability_slots(
            start_from=start_from,
            end_to=end_to,
            slot_minutes=slot_minutes,
            busy=busy_intervals,
        )
        availability.append(
            AppointmentAvailability(
                provider_id=provider_id,
                location=provider_location,
                slots=slots,
            )
        )

    return availability


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
        metadata=ensure_appointment_metadata(patient_id=appointment.patient_id),
        context=context or {},
    )

    session.commit()
    session.refresh(appointment)
    notify_appointment_created(session, appointment)
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
        metadata=ensure_appointment_metadata(patient_id=appointment.patient_id),
        context=context or {},
    )

    session.commit()
    session.refresh(appointment)
    return _build_appointment_read(session, appointment)


def _collect_alternative_slots(
    session: Session,
    *,
    appointment: Appointment,
    desired_start: datetime,
    desired_end: datetime,
) -> List[AvailabilitySlot]:
    slot_minutes = max(int((desired_end - desired_start).total_seconds() // 60), 1)
    window_end = min(desired_start + timedelta(hours=8), desired_start + timedelta(days=1))
    availabilities = search_availability(
        session,
        start_from=desired_start,
        end_to=window_end,
        provider_ids=[appointment.provider_id],
        location=appointment.location,
        slot_minutes=slot_minutes,
        exclude_appointment_id=appointment.id,
    )
    slots: List[AvailabilitySlot] = []
    for entry in availabilities:
        slots.extend(entry.slots)
        if len(slots) >= 5:
            break
    return slots[:5]


def reschedule_appointment(
    session: Session,
    *,
    appointment_id: int,
    data: AppointmentRescheduleRequest,
    actor_id: Optional[int],
    context: Optional[dict] = None,
) -> AppointmentRead:
    appointment = session.get(Appointment, appointment_id)
    if not appointment:
        raise AppointmentNotFoundError

    new_start = data.start_time
    new_end = data.end_time
    if new_start >= new_end:
        raise AppointmentConflictError("INVALID_TIME_RANGE")

    try:
        _check_overlap(
            session,
            provider_id=appointment.provider_id,
            start_time=new_start,
            end_time=new_end,
            exclude_id=appointment.id,
        )
    except AppointmentConflictError as exc:
        alternatives = _collect_alternative_slots(
            session,
            appointment=appointment,
            desired_start=new_start,
            desired_end=new_end,
        )
        raise AppointmentConflictError(
            exc.code,
            message=str(exc),
            alternatives=alternatives,
        ) from exc

    previous_start = appointment.start_time
    previous_end = appointment.end_time

    appointment.start_time = new_start
    appointment.end_time = new_end
    appointment.updated_at = datetime.utcnow()
    appointment.status = "scheduled"

    note_parts = [
        f"from={previous_start.isoformat()}",
        f"to={previous_end.isoformat()}",
    ]
    if appointment.location:
        note_parts.append(f"location={appointment.location}")
    if data.reason:
        note_parts.append(f"reason={data.reason}")
    note = "; ".join(note_parts)

    _add_status_history(session, appointment.id, "rescheduled", actor_id, note)

    audit.record_event(
        session,
        actor_id=actor_id,
        action="appointment.reschedule",
        resource_type="appointment",
        resource_id=str(appointment.id),
        metadata=ensure_appointment_metadata(
            patient_id=appointment.patient_id,
            previous_start=previous_start.isoformat(),
            previous_end=previous_end.isoformat(),
            reason=data.reason,
        ),
        context=context or {},
    )

    session.commit()
    session.refresh(appointment)

    notify_appointment_rescheduled(
        session,
        appointment,
        previous_start=previous_start.isoformat(),
        previous_end=previous_end.isoformat(),
        reason=data.reason,
    )

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
        metadata=ensure_appointment_metadata(
            patient_id=appointment.patient_id,
            reason=request.reason,
            notify=request.notify_patient,
        ),
        context=context or {},
    )

    session.commit()
    session.refresh(appointment)
    if request.notify_patient:
        notify_appointment_cancelled(
            session,
            appointment,
            reason=request.reason,
        )
    return _build_appointment_read(session, appointment)
