from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import AuthenticatedUser, get_audit_context, get_current_user, get_db, require_roles
from app.schemas import (
    Pagination,
    PatientCreate,
    PatientMergeRequest,
    PatientRead,
    PatientSummary,
    PatientUpdate,
)
from app.services import (
    PatientConflictError,
    PatientMergeError,
    PatientNotFoundError,
    archive_patient,
    create_patient,
    get_patient,
    list_patients,
    merge_patients,
    patch_patient,
    update_patient,
)

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/", response_model=Pagination[PatientSummary])
def list_patient_records(
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    status_filter: str | None = None,
    session: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_roles("doctor", "nurse", "admin")),
) -> Pagination[PatientSummary]:
    items, total = list_patients(
        session,
        page=page,
        page_size=min(page_size, 100),
        search=search,
        status=status_filter,
    )
    return Pagination[PatientSummary](items=items, page=page, page_size=page_size, total=total)


@router.post("/", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient_record(
    payload: PatientCreate,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor", "nurse", "admin")),
    context: dict = Depends(get_audit_context),
) -> PatientRead:
    try:
        return create_patient(session, data=payload, actor_id=current.user.id, context=context)
    except PatientConflictError as exc:
        detail = {"detail": "Potilas on jo olemassa", "code": exc.code}
        detail.update(exc.payload)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


@router.get("/{patient_id}", response_model=PatientRead)
def get_patient_record(
    patient_id: int,
    session: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_roles("doctor", "nurse", "admin")),
) -> PatientRead:
    try:
        return get_patient(session, patient_id)
    except PatientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Potilasta ei löydy") from exc


@router.put("/{patient_id}", response_model=PatientRead)
def replace_patient_record(
    patient_id: int,
    payload: PatientCreate,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor", "nurse", "admin")),
    context: dict = Depends(get_audit_context),
) -> PatientRead:
    try:
        return update_patient(
            session,
            patient_id=patient_id,
            data=payload,
            actor_id=current.user.id,
            reason="Täysi päivitys",
            context=context,
        )
    except PatientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Potilasta ei löydy") from exc
    except PatientConflictError as exc:
        detail = {"detail": "Potilas on jo olemassa", "code": exc.code}
        detail.update(exc.payload)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


@router.patch("/{patient_id}", response_model=PatientRead)
def patch_patient_record(
    patient_id: int,
    payload: PatientUpdate,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor", "nurse", "admin")),
    context: dict = Depends(get_audit_context),
) -> PatientRead:
    try:
        return patch_patient(
            session,
            patient_id=patient_id,
            data=payload,
            actor_id=current.user.id,
            context=context,
        )
    except PatientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Potilasta ei löydy") from exc
    except PatientConflictError as exc:
        detail = {"detail": "Potilas on jo olemassa", "code": exc.code}
        detail.update(exc.payload)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


@router.post("/{patient_id}/merge", response_model=PatientRead)
def merge_patient_record(
    patient_id: int,
    payload: PatientMergeRequest,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("admin")),
    context: dict = Depends(get_audit_context),
) -> PatientRead:
    try:
        return merge_patients(
            session,
            target_patient_id=patient_id,
            source_patient_id=payload.source_patient_id,
            actor_id=current.user.id,
            context=context,
        )
    except PatientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Potilasta ei löydy") from exc
    except PatientMergeError as exc:
        detail = {"detail": exc.message, "code": exc.code}
        detail.update(exc.payload)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_patient_record(
    patient_id: int,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("admin")),
    context: dict = Depends(get_audit_context),
) -> None:
    try:
        archive_patient(session, patient_id=patient_id, actor_id=current.user.id, context=context)
    except PatientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Potilasta ei löydy") from exc
