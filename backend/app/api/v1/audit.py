from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import AuthenticatedUser, get_db, require_roles
from app.schemas import AuditEventRead, Pagination
from app.models import AuditEvent
from app.services import audit

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/", response_model=Pagination[AuditEventRead])
def list_audit_events(
    page: int = 1,
    page_size: int = 25,
    resource_type: str | None = None,
    resource_id: str | None = None,
    actor_id: int | None = None,
    action: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    session: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> Pagination[AuditEventRead]:
    items, total = audit.query_events(
        session,
        resource_type=resource_type,
        resource_id=resource_id,
        actor_id=actor_id,
        action=action,
        from_ts=from_ts,
        to_ts=to_ts,
        page=page,
        page_size=min(page_size, 100),
    )
    return Pagination[AuditEventRead](items=items, page=page, page_size=page_size, total=total)


@router.get("/{audit_id}", response_model=AuditEventRead)
def get_audit_event(
    audit_id: int,
    session: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_roles("admin")),
) -> AuditEventRead:
    event = session.get(AuditEvent, audit_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lokimerkintää ei löydy")
    return AuditEventRead.model_validate(event)
