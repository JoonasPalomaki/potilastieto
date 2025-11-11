from __future__ import annotations

from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from sqlmodel import Session, func, select

from app.models import AuditEvent
from app.services.audit_policy import sanitize_metadata


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
        metadata_json=sanitize_metadata(resource_type, action, metadata),
        context=context or {},
        timestamp=datetime.utcnow(),
    )
    session.add(event)
    return event


def log_read(
    resource_type: str,
    *,
    many: bool = False,
    action: Optional[str] = None,
    metadata_getter: Optional[Callable[[Any, Dict[str, Any]], Dict[str, Any]]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for logging read access in service functions.

    Parameters
    ----------
    resource_type:
        The logical type of the resource that is being accessed.
    many:
        Whether the wrapped function returns a collection of resources.
    action:
        Optional custom action name. Defaults to ``"{resource_type}.read"`` for
        single resource access and ``"{resource_type}.list"`` for collection
        queries.
    metadata_getter:
        Optional callable producing additional metadata based on the function
        result and the keyword arguments passed to the wrapped function.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            actor_id = kwargs.pop("audit_actor_id", None)
            context = kwargs.pop("audit_context", None) or {}
            call_kwargs = kwargs.copy()
            session: Optional[Session] = call_kwargs.get("session")
            if session is None and args:
                session = next((arg for arg in args if isinstance(arg, Session)), None)

            result = func(*args, **kwargs)

            if session is None or actor_id is None:
                return result

            resolved_action = action or (f"{resource_type}.list" if many else f"{resource_type}.read")
            metadata_base = metadata_getter(result, call_kwargs) if metadata_getter else {}

            events_created = 0

            if many:
                collection, *_ = (result if isinstance(result, tuple) else (result,))
                items = collection or []
                ids = [getattr(item, "id", None) for item in items]
                ids = [str(resource_id) for resource_id in ids if resource_id is not None]

                if not ids:
                    metadata = dict(metadata_base)
                    metadata.setdefault("result_count", 0)
                    record_event(
                        session,
                        actor_id=actor_id,
                        action=resolved_action,
                        resource_type=resource_type,
                        resource_id=None,
                        metadata=metadata,
                        context=context,
                    )
                    events_created += 1
                else:
                    for resource_id in ids:
                        metadata = dict(metadata_base)
                        metadata.setdefault("result_count", len(ids))
                        record_event(
                            session,
                            actor_id=actor_id,
                            action=resolved_action,
                            resource_type=resource_type,
                            resource_id=resource_id,
                            metadata=metadata,
                            context=context,
                        )
                        events_created += 1
            else:
                target = result[0] if isinstance(result, tuple) else result
                resource_id = getattr(target, "id", None)
                metadata = dict(metadata_base)
                record_event(
                    session,
                    actor_id=actor_id,
                    action=resolved_action,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id is not None else None,
                    metadata=metadata,
                    context=context,
                )
                events_created += 1

            if events_created:
                session.commit()

            return result

        return wrapper

    return decorator


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
