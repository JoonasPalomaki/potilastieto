from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import AuthenticatedUser, get_audit_context, get_db, require_roles
from app.schemas import (
    InitialVisitCreate,
    InitialVisitRead,
    VisitBasicsPanelRead,
    VisitBasicsPanelUpdate,
    VisitDiagnosesPanelRead,
    VisitDiagnosesPanelUpdate,
    VisitNarrativePanelRead,
    VisitNarrativePanelUpdate,
    VisitOrdersPanelRead,
    VisitOrdersPanelUpdate,
    VisitReasonPanelRead,
    VisitReasonPanelUpdate,
    VisitSummaryPanelRead,
)
from app.services import (
    VisitAppointmentNotFoundError,
    VisitConflictError,
    VisitNotFoundError,
    VisitPatientNotFoundError,
    create_initial_visit,
    get_initial_visit,
    update_visit_anamnesis,
    update_visit_basics,
    update_visit_diagnoses,
    update_visit_orders,
    update_visit_reason,
    update_visit_status,
    update_visit_summary,
)

router = APIRouter(prefix="/visits", tags=["visits"])


def _visit_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ensikäyntiä ei löydy")


def _visit_conflict(exc: VisitConflictError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"message": exc.message, "code": exc.code},
    )


@router.get("/{visit_id}", response_model=InitialVisitRead)
def read_visit(
    visit_id: int,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor")),
    context: dict = Depends(get_audit_context),
) -> InitialVisitRead:
    try:
        return get_initial_visit(
            session,
            visit_id,
            audit_actor_id=current.user.id,
            audit_context=context,
        )
    except VisitNotFoundError as exc:
        raise _visit_not_found() from exc


@router.post("/", response_model=InitialVisitRead, status_code=status.HTTP_201_CREATED)
def create_visit(
    payload: InitialVisitCreate,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor")),
    context: dict = Depends(get_audit_context),
) -> InitialVisitRead:
    try:
        return create_initial_visit(
            session,
            data=payload,
            actor_id=current.user.id,
            context=context,
        )
    except VisitAppointmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ajanvarausta ei löydy") from exc
    except VisitPatientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Potilasta ei löydy") from exc
    except VisitConflictError as exc:
        raise _visit_conflict(exc) from exc


@router.put("/{visit_id}/basics", response_model=VisitBasicsPanelRead)
def update_basics(
    visit_id: int,
    payload: VisitBasicsPanelUpdate,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor")),
    context: dict = Depends(get_audit_context),
) -> VisitBasicsPanelRead:
    try:
        return update_visit_basics(
            session,
            visit_id,
            data=payload,
            actor_id=current.user.id,
            context=context,
        )
    except VisitNotFoundError as exc:
        raise _visit_not_found() from exc


@router.put("/{visit_id}/reason", response_model=VisitReasonPanelRead)
def update_reason(
    visit_id: int,
    payload: VisitReasonPanelUpdate,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor")),
    context: dict = Depends(get_audit_context),
) -> VisitReasonPanelRead:
    try:
        return update_visit_reason(
            session,
            visit_id,
            data=payload,
            actor_id=current.user.id,
            context=context,
        )
    except VisitNotFoundError as exc:
        raise _visit_not_found() from exc


@router.put("/{visit_id}/anamnesis", response_model=VisitNarrativePanelRead)
def update_anamnesis(
    visit_id: int,
    payload: VisitNarrativePanelUpdate,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor")),
    context: dict = Depends(get_audit_context),
) -> VisitNarrativePanelRead:
    try:
        return update_visit_anamnesis(
            session,
            visit_id,
            data=payload,
            actor_id=current.user.id,
            context=context,
        )
    except VisitNotFoundError as exc:
        raise _visit_not_found() from exc


@router.put("/{visit_id}/status", response_model=VisitNarrativePanelRead)
def update_status(
    visit_id: int,
    payload: VisitNarrativePanelUpdate,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor")),
    context: dict = Depends(get_audit_context),
) -> VisitNarrativePanelRead:
    try:
        return update_visit_status(
            session,
            visit_id,
            data=payload,
            actor_id=current.user.id,
            context=context,
        )
    except VisitNotFoundError as exc:
        raise _visit_not_found() from exc


@router.put("/{visit_id}/diagnoses", response_model=VisitDiagnosesPanelRead)
def update_diagnoses(
    visit_id: int,
    payload: VisitDiagnosesPanelUpdate,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor")),
    context: dict = Depends(get_audit_context),
) -> VisitDiagnosesPanelRead:
    try:
        return update_visit_diagnoses(
            session,
            visit_id,
            data=payload,
            actor_id=current.user.id,
            context=context,
        )
    except VisitNotFoundError as exc:
        raise _visit_not_found() from exc


@router.put("/{visit_id}/orders", response_model=VisitOrdersPanelRead)
def update_orders(
    visit_id: int,
    payload: VisitOrdersPanelUpdate,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor")),
    context: dict = Depends(get_audit_context),
) -> VisitOrdersPanelRead:
    try:
        return update_visit_orders(
            session,
            visit_id,
            data=payload,
            actor_id=current.user.id,
            context=context,
        )
    except VisitNotFoundError as exc:
        raise _visit_not_found() from exc


@router.put("/{visit_id}/summary", response_model=VisitSummaryPanelRead)
def update_summary(
    visit_id: int,
    payload: VisitNarrativePanelUpdate,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor")),
    context: dict = Depends(get_audit_context),
) -> VisitSummaryPanelRead:
    try:
        return update_visit_summary(
            session,
            visit_id,
            data=payload,
            actor_id=current.user.id,
            context=context,
        )
    except VisitNotFoundError as exc:
        raise _visit_not_found() from exc
