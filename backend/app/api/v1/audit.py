from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
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
    current: AuthenticatedUser = Depends(require_roles("admin", "doctor", "nurse")),
    format: str | None = None,
) -> Pagination[AuditEventRead]:
    role_code = current.role.code if current.role else None
    effective_page_size = min(page_size, 100)

    if role_code != "admin":
        if resource_type not in {"patient", "appointment"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="resource_type must be 'patient' or 'appointment' for clinical staff",
            )
        if resource_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="resource_id filter is required for doctor and nurse queries",
            )
        permissions = set(current.role.permissions if current.role else [])
        required_permission = "patients:read" if resource_type == "patient" else "appointments:write"
        if required_permission not in permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    items, total = audit.query_events(
        session,
        resource_type=resource_type,
        resource_id=resource_id,
        actor_id=actor_id,
        action=action,
        from_ts=from_ts,
        to_ts=to_ts,
        page=page,
        page_size=effective_page_size,
    )
    events = [AuditEventRead.model_validate(item) for item in items]

    if format is not None:
        if format.lower() != "csv":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported format. Available options: csv",
            )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "timestamp",
                "actor_id",
                "action",
                "resource_type",
                "resource_id",
                "metadata",
                "context",
            ]
        )
        for event in events:
            writer.writerow(
                [
                    event.id,
                    event.timestamp.isoformat(),
                    event.actor_id,
                    event.action,
                    event.resource_type,
                    event.resource_id,
                    json.dumps(event.metadata, ensure_ascii=False),
                    json.dumps(event.context, ensure_ascii=False),
                ]
            )
        csv_data = output.getvalue()
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit-events.csv"},
        )

    return Pagination[AuditEventRead](items=events, page=page, page_size=page_size, total=total)


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
