from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.api.deps import AuthenticatedUser, get_audit_context, get_db, require_roles
from app.schemas import (
    AppointmentCancelRequest,
    AppointmentCreate,
    AppointmentAvailability,
    AppointmentRead,
    AppointmentRescheduleRequest,
    AppointmentSummary,
    AppointmentUpdate,
    Pagination,
)
from app.services import (
    AppointmentConflictError,
    AppointmentNotFoundError,
    cancel_appointment,
    create_appointment,
    get_appointment,
    list_appointments,
    reschedule_appointment,
    search_availability,
    update_appointment,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])


def _conflict_error(exc: AppointmentConflictError) -> HTTPException:
    if exc.code == "PROVIDER_OVERLAP":
        message = "Aika on jo varattu"
    elif exc.code == "INVALID_TIME_RANGE":
        message = "Aikaväli on virheellinen"
    else:
        message = "Ajanvarauksessa on ristiriita"

    payload = {"message": message, "code": exc.code}
    if exc.alternatives:
        payload["alternatives"] = [slot.model_dump() for slot in exc.alternatives]
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=payload)


@router.get("/availability", response_model=List[AppointmentAvailability])
def list_availability(
    start_from: datetime,
    end_to: datetime,
    provider_ids: List[int] = Query(..., alias="provider_id"),
    location: str | None = None,
    slot_minutes: int = 30,
    exclude_appointment_id: int | None = None,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor", "nurse", "admin")),
    context: dict = Depends(get_audit_context),
) -> List[AppointmentAvailability]:
    try:
        return search_availability(
            session,
            start_from=start_from,
            end_to=end_to,
            provider_ids=provider_ids,
            location=location,
            slot_minutes=slot_minutes,
            exclude_appointment_id=exclude_appointment_id,
            audit_actor_id=current.user.id,
            audit_context=context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/", response_model=Pagination[AppointmentSummary])
def list_appointment_records(
    page: int = 1,
    page_size: int = 25,
    patient_id: int | None = None,
    provider_id: int | None = None,
    status_filter: str | None = None,
    start_from: datetime | None = None,
    end_to: datetime | None = None,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor", "nurse", "admin")),
    context: dict = Depends(get_audit_context),
) -> Pagination[AppointmentSummary]:
    items, total = list_appointments(
        session,
        page=page,
        page_size=min(page_size, 100),
        patient_id=patient_id,
        provider_id=provider_id,
        status=status_filter,
        start_from=start_from,
        end_to=end_to,
        audit_actor_id=current.user.id,
        audit_context=context,
    )
    return Pagination[AppointmentSummary](items=items, page=page, page_size=page_size, total=total)


@router.post("/", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
def create_appointment_record(
    payload: AppointmentCreate,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor", "nurse", "admin")),
    context: dict = Depends(get_audit_context),
) -> AppointmentRead:
    try:
        return create_appointment(session, data=payload, actor_id=current.user.id, context=context)
    except AppointmentConflictError as exc:
        raise _conflict_error(exc) from exc


@router.get("/{appointment_id}", response_model=AppointmentRead)
def get_appointment_record(
    appointment_id: int,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor", "nurse", "admin")),
    context: dict = Depends(get_audit_context),
) -> AppointmentRead:
    try:
        return get_appointment(
            session,
            appointment_id,
            audit_actor_id=current.user.id,
            audit_context=context,
        )
    except AppointmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ajanvarausta ei löydy") from exc


@router.put("/{appointment_id}", response_model=AppointmentRead)
def update_appointment_record(
    appointment_id: int,
    payload: AppointmentUpdate,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor", "nurse", "admin")),
    context: dict = Depends(get_audit_context),
) -> AppointmentRead:
    try:
        return update_appointment(
            session,
            appointment_id=appointment_id,
            data=payload,
            actor_id=current.user.id,
            context=context,
        )
    except AppointmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ajanvarausta ei löydy") from exc
    except AppointmentConflictError as exc:
        raise _conflict_error(exc) from exc


@router.post("/{appointment_id}/cancel", response_model=AppointmentRead)
def cancel_appointment_record(
    appointment_id: int,
    payload: AppointmentCancelRequest,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor", "nurse", "admin")),
    context: dict = Depends(get_audit_context),
) -> AppointmentRead:
    try:
        return cancel_appointment(
            session,
            appointment_id=appointment_id,
            request=payload,
            actor_id=current.user.id,
            context=context,
        )
    except AppointmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ajanvarausta ei löydy") from exc


@router.post("/{appointment_id}/reschedule", response_model=AppointmentRead)
def reschedule_appointment_record(
    appointment_id: int,
    payload: AppointmentRescheduleRequest,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor", "nurse", "admin")),
    context: dict = Depends(get_audit_context),
) -> AppointmentRead:
    try:
        return reschedule_appointment(
            session,
            appointment_id=appointment_id,
            data=payload,
            actor_id=current.user.id,
            context=context,
        )
    except AppointmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ajanvarausta ei löydy") from exc
    except AppointmentConflictError as exc:
        raise _conflict_error(exc) from exc
