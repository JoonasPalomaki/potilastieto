from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Tuple

from sqlmodel import Session, func, select

from app.models import AuditEvent


def record_event(
    session: Session,
    *,
    actor_id: Optional[int],
    action: str,
    resource_type: str,
    resource_id: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=metadata or {},
        context=context or {},
        timestamp=datetime.utcnow(),
    )
    session.add(event)
    return event


def query_events(
    session: Session,
    *,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    actor_id: Optional[int] = None,
    action: Optional[str] = None,
    from_ts: Optional[datetime] = None,
    to_ts: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 25,
) -> Tuple[Iterable[AuditEvent], int]:
    statement = select(AuditEvent)
    count_stmt = select(func.count()).select_from(AuditEvent)

    def apply_filters(stmt):
        if resource_type:
            stmt = stmt.where(AuditEvent.resource_type == resource_type)
        if resource_id:
            stmt = stmt.where(AuditEvent.resource_id == resource_id)
        if actor_id:
            stmt = stmt.where(AuditEvent.actor_id == actor_id)
        if action:
            stmt = stmt.where(AuditEvent.action == action)
        if from_ts:
            stmt = stmt.where(AuditEvent.timestamp >= from_ts)
        if to_ts:
            stmt = stmt.where(AuditEvent.timestamp <= to_ts)
        return stmt

    statement = apply_filters(statement).order_by(AuditEvent.timestamp.desc())
    count_stmt = apply_filters(count_stmt)

    total = session.exec(count_stmt).one()
    items = session.exec(
        statement.offset((page - 1) * page_size).limit(page_size)
    ).all()
    return items, total
