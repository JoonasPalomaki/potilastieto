from __future__ import annotations

import io
from dataclasses import asdict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlmodel import Session

from app.api.deps import AuthenticatedUser, get_audit_context, get_db, require_roles
from app.schemas import (
    DiagnosisCodeImportResponse,
    DiagnosisCodeImportSummary,
    DiagnosisCodeRead,
    DiagnosisCodeSearchResponse,
)
from app.services import import_diagnosis_codes, search_diagnosis_codes

router = APIRouter(prefix="/diagnosis-codes", tags=["diagnosis codes"])


@router.get("/", response_model=DiagnosisCodeSearchResponse)
def search_codes(
    *,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    include_deleted: bool = False,
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("doctor", "nurse", "admin")),
) -> DiagnosisCodeSearchResponse:
    del current  # roles already enforced
    query_page_size = min(max(page_size, 1), 200)
    items, total = search_diagnosis_codes(
        session,
        search=search,
        include_deleted=include_deleted,
        page=page,
        page_size=query_page_size,
    )
    payload = [DiagnosisCodeRead.model_validate(item) for item in items]
    return DiagnosisCodeSearchResponse(
        items=payload,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/import", response_model=DiagnosisCodeImportResponse, status_code=status.HTTP_200_OK)
async def import_codes(
    *,
    csv_file: UploadFile = File(...),
    session: Session = Depends(get_db),
    current: AuthenticatedUser = Depends(require_roles("admin")),
    context: dict = Depends(get_audit_context),
) -> DiagnosisCodeImportResponse:
    raw = await csv_file.read()
    if raw is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tyhjä tiedosto")
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV täytyy olla UTF-8 muodossa",
        ) from exc

    buffer = io.StringIO(decoded)
    try:
        result = import_diagnosis_codes(
            session,
            csv_stream=buffer,
            actor_id=current.user.id,
            context=context,
            filename=csv_file.filename,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    summary = DiagnosisCodeImportSummary(**asdict(result))
    return DiagnosisCodeImportResponse(filename=csv_file.filename, summary=summary)
