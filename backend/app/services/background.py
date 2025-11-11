from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List

from sqlmodel import select

from app.core.config import settings
from app.db.session import get_session
from app.models import Appointment, AppointmentStatusHistory, RefreshToken
from app.services import audit
from app.services.audit_policy import ensure_appointment_metadata


class BackgroundService:
    def __init__(self, interval_seconds: int) -> None:
        self.interval_seconds = interval_seconds
        self._tasks: List[asyncio.Task] = []
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tasks.append(asyncio.create_task(self._run()))

    async def shutdown(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self._running = False

    async def _run(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.interval_seconds)
                await asyncio.to_thread(self._cleanup_once)
            except asyncio.CancelledError:
                break

    def _cleanup_once(self) -> None:
        now = datetime.now(timezone.utc)
        with get_session() as session:
            expired_tokens = session.exec(
                select(RefreshToken).where(RefreshToken.expires_at < now)
            ).all()
            for token in expired_tokens:
                session.delete(token)

            overdue = session.exec(
                select(Appointment).where(
                    Appointment.status == "scheduled",
                    Appointment.end_time < now,
                )
            ).all()
            for appointment in overdue:
                appointment.status = "completed"
                appointment.updated_at = now
                session.add(
                    AppointmentStatusHistory(
                        appointment_id=appointment.id,
                        status="completed",
                        changed_by=None,
                        changed_at=now,
                        note="Auto-completed by background service",
                    )
                )
                audit.record_event(
                    session,
                    actor_id=None,
                    action="appointment.complete",
                    resource_type="appointment",
                    resource_id=str(appointment.id),
                    metadata=ensure_appointment_metadata(auto=True),
                    context={"source": "background"},
                )

            session.commit()


_service: BackgroundService | None = None


def start_background_services() -> None:
    global _service
    if _service is None:
        _service = BackgroundService(settings.background_cleanup_interval_seconds)
        _service.start()


def stop_background_services() -> None:
    global _service
    if _service is not None:
        service = _service
        _service = None
        asyncio.create_task(service.shutdown())
