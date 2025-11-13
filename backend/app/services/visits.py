from __future__ import annotations

import json
from typing import Dict, Iterable, List, Optional

from sqlmodel import Session, select

from app.models import Appointment, ClinicalNote, Order, Patient, Visit
from app.schemas import (
    InitialVisitCreate,
    InitialVisitRead,
    OrderRead,
    VisitBasicsPanelRead,
    VisitBasicsPanelUpdate,
    VisitDiagnosesPanelRead,
    VisitDiagnosesPanelUpdate,
    VisitDiagnosisEntry,
    VisitNarrativePanelRead,
    VisitNarrativePanelUpdate,
    VisitOrderItem,
    VisitOrdersPanelRead,
    VisitOrdersPanelUpdate,
    VisitReasonPanelRead,
    VisitReasonPanelUpdate,
    VisitSummaryPanelRead,
)
from app.services import audit
from app.services.audit_policy import make_patient_reference


NOTE_TITLES: Dict[str, str] = {
    "visit.anamnesis": "Anamneesi",
    "visit.status": "Status",
    "visit.summary": "Yhteenveto",
    "visit.diagnoses": "Diagnoosit",
}


class VisitNotFoundError(Exception):
    """Raised when a visit cannot be located."""


class VisitConflictError(Exception):
    """Raised when a visit operation conflicts with existing data."""

    def __init__(self, code: str, message: Optional[str] = None) -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


class VisitAppointmentNotFoundError(Exception):
    """Raised when the appointment for a new visit does not exist."""


class VisitPatientNotFoundError(Exception):
    """Raised when the patient for a new visit does not exist."""


def _get_visit(session: Session, visit_id: int) -> Visit:
    visit = session.get(Visit, visit_id)
    if not visit:
        raise VisitNotFoundError
    return visit


def _note_query(session: Session, visit_id: int, note_type: str) -> ClinicalNote | None:
    return session.exec(
        select(ClinicalNote).where(
            ClinicalNote.visit_id == visit_id,
            ClinicalNote.note_type == note_type,
        )
    ).first()


def _visit_metadata(visit: Visit, *, panel: Optional[str] = None) -> Dict[str, object]:
    metadata: Dict[str, object] = {"patient_ref": make_patient_reference(visit.patient_id)}
    if visit.appointment_id is not None:
        metadata["appointment_id"] = visit.appointment_id
    if panel:
        metadata["panel"] = panel
    return metadata


def _build_text_panel(note: Optional[ClinicalNote]) -> VisitNarrativePanelRead:
    if not note:
        return VisitNarrativePanelRead(content=None, author_id=None, updated_at=None)
    return VisitNarrativePanelRead(
        content=note.content,
        author_id=note.author_id,
        updated_at=note.updated_at,
    )


def _build_diagnoses_panel(note: Optional[ClinicalNote]) -> VisitDiagnosesPanelRead:
    if not note:
        return VisitDiagnosesPanelRead(diagnoses=[])
    try:
        payload = json.loads(note.content)
    except json.JSONDecodeError:
        payload = []
    diagnoses: List[VisitDiagnosisEntry] = []
    for item in payload or []:
        try:
            diagnoses.append(VisitDiagnosisEntry.model_validate(item))
        except Exception:  # noqa: BLE001
            continue
    return VisitDiagnosesPanelRead(
        diagnoses=diagnoses,
        author_id=note.author_id,
        updated_at=note.updated_at,
    )


def _build_orders_panel(session: Session, visit_id: int) -> VisitOrdersPanelRead:
    orders = session.exec(
        select(Order)
        .where(Order.visit_id == visit_id)
        .order_by(Order.created_at.asc())
    ).all()
    order_models: List[OrderRead] = []
    for order in orders:
        order_models.append(
            OrderRead(
                id=order.id,
                visit_id=order.visit_id,
                patient_id=order.patient_id,
                ordered_by_id=order.ordered_by_id,
                order_type=order.order_type,
                status=order.status,
                details=order.details,
                placed_at=order.placed_at,
                created_at=order.created_at,
                updated_at=order.updated_at,
            )
        )
    return VisitOrdersPanelRead(orders=order_models)


def _build_initial_visit_read(session: Session, visit: Visit) -> InitialVisitRead:
    notes = session.exec(
        select(ClinicalNote).where(ClinicalNote.visit_id == visit.id)
    ).all()
    notes_by_type = {note.note_type: note for note in notes}

    basics = VisitBasicsPanelRead(
        visit_type=visit.visit_type,
        location=visit.location,
        started_at=visit.started_at,
        ended_at=visit.ended_at,
        attending_provider_id=visit.attending_provider_id,
        updated_at=visit.updated_at,
    )
    reason = VisitReasonPanelRead(
        reason=visit.reason,
        updated_at=visit.updated_at,
    )
    anamnesis = _build_text_panel(notes_by_type.get("visit.anamnesis"))
    status = _build_text_panel(notes_by_type.get("visit.status"))
    summary_note = notes_by_type.get("visit.summary")
    summary = VisitSummaryPanelRead(
        content=summary_note.content if summary_note else None,
        author_id=summary_note.author_id if summary_note else None,
        updated_at=summary_note.updated_at if summary_note else None,
    )
    diagnoses = _build_diagnoses_panel(notes_by_type.get("visit.diagnoses"))
    orders = _build_orders_panel(session, visit.id)

    return InitialVisitRead(
        id=visit.id,
        patient_id=visit.patient_id,
        appointment_id=visit.appointment_id,
        basics=basics,
        reason=reason,
        anamnesis=anamnesis,
        status=status,
        diagnoses=diagnoses,
        orders=orders,
        summary=summary,
        created_at=visit.created_at,
        updated_at=visit.updated_at,
    )


def _upsert_note(
    session: Session,
    visit: Visit,
    *,
    note_type: str,
    content: str,
    actor_id: Optional[int],
) -> ClinicalNote:
    note = _note_query(session, visit.id, note_type)
    if note:
        note.content = content
        note.author_id = actor_id
    else:
        note = ClinicalNote(
            visit_id=visit.id,
            patient_id=visit.patient_id,
            author_id=actor_id,
            note_type=note_type,
            title=NOTE_TITLES.get(note_type, "Muistiinpano"),
            content=content,
        )
        session.add(note)
    session.flush()
    return note


def _upsert_diagnoses(
    session: Session,
    visit: Visit,
    data: VisitDiagnosesPanelUpdate,
    actor_id: Optional[int],
) -> ClinicalNote:
    payload = [entry.model_dump() for entry in data.diagnoses]
    content = json.dumps(payload, ensure_ascii=False)
    return _upsert_note(
        session,
        visit,
        note_type="visit.diagnoses",
        content=content,
        actor_id=actor_id,
    )


def _replace_orders(
    session: Session,
    visit: Visit,
    orders: Iterable[VisitOrderItem],
    actor_id: Optional[int],
) -> None:
    existing = session.exec(select(Order).where(Order.visit_id == visit.id)).all()
    for order in existing:
        session.delete(order)
    session.flush()

    for item in orders:
        order = Order(
            visit_id=visit.id,
            patient_id=visit.patient_id,
            ordered_by_id=item.ordered_by_id or actor_id,
            order_type=item.order_type,
            status=item.status or "draft",
            details=item.details,
            placed_at=item.placed_at,
        )
        session.add(order)
    session.flush()


@audit.log_read("visit")
def get_initial_visit(session: Session, visit_id: int) -> InitialVisitRead:
    visit = _get_visit(session, visit_id)
    return _build_initial_visit_read(session, visit)


def create_initial_visit(
    session: Session,
    *,
    data: InitialVisitCreate,
    actor_id: Optional[int],
    context: Optional[dict] = None,
) -> InitialVisitRead:
    appointment: Optional[Appointment] = None
    patient_id: int

    if data.appointment_id is not None:
        appointment = session.get(Appointment, data.appointment_id)
        if not appointment:
            raise VisitAppointmentNotFoundError

        existing = session.exec(
            select(Visit).where(Visit.appointment_id == appointment.id)
        ).first()
        if existing:
            raise VisitConflictError(
                "VISIT_EXISTS", "Ensikäynti on jo luotu tälle ajanvaraukselle"
            )

        patient_id = appointment.patient_id
    else:
        patient = session.get(Patient, data.patient_id)
        if not patient:
            raise VisitPatientNotFoundError
        patient_id = patient.id

    basics = data.basics
    visit = Visit(
        patient_id=patient_id,
        appointment_id=appointment.id if appointment else None,
        visit_type=(basics.visit_type if basics else None),
        location=(
            basics.location
            if basics and basics.location is not None
            else (appointment.location if appointment else None)
        ),
        started_at=(
            basics.started_at
            if basics and basics.started_at
            else (appointment.start_time if appointment else None)
        ),
        ended_at=(
            basics.ended_at
            if basics and basics.ended_at
            else (appointment.end_time if appointment else None)
        ),
        attending_provider_id=(
            basics.attending_provider_id
            if basics and basics.attending_provider_id is not None
            else (appointment.provider_id if appointment else None)
        ),
        reason=data.reason.reason if data.reason else (appointment.notes if appointment else None),
        status="in_progress",
    )

    session.add(visit)
    session.flush()

    if data.anamnesis:
        _upsert_note(
            session,
            visit,
            note_type="visit.anamnesis",
            content=data.anamnesis.content,
            actor_id=actor_id,
        )
    if data.status:
        _upsert_note(
            session,
            visit,
            note_type="visit.status",
            content=data.status.content,
            actor_id=actor_id,
        )
    if data.summary:
        _upsert_note(
            session,
            visit,
            note_type="visit.summary",
            content=data.summary.content,
            actor_id=actor_id,
        )
    if data.diagnoses:
        _upsert_diagnoses(session, visit, data.diagnoses, actor_id)
    if data.orders:
        _replace_orders(session, visit, data.orders.orders, actor_id)

    audit.record_event(
        session,
        actor_id=actor_id,
        action="visit.create",
        resource_type="visit",
        resource_id=str(visit.id),
        metadata=_visit_metadata(visit),
        context=context or {},
    )

    session.commit()
    session.refresh(visit)
    return _build_initial_visit_read(session, visit)


def update_visit_basics(
    session: Session,
    visit_id: int,
    *,
    data: VisitBasicsPanelUpdate,
    actor_id: Optional[int],
    context: Optional[dict] = None,
) -> VisitBasicsPanelRead:
    visit = _get_visit(session, visit_id)

    if data.visit_type is not None:
        visit.visit_type = data.visit_type
    if data.location is not None:
        visit.location = data.location
    if data.started_at is not None:
        visit.started_at = data.started_at
    if data.ended_at is not None:
        visit.ended_at = data.ended_at
    if data.attending_provider_id is not None:
        visit.attending_provider_id = data.attending_provider_id

    audit.record_event(
        session,
        actor_id=actor_id,
        action="visit.update.basics",
        resource_type="visit",
        resource_id=str(visit.id),
        metadata=_visit_metadata(visit, panel="basics"),
        context=context or {},
    )

    session.commit()
    session.refresh(visit)

    return VisitBasicsPanelRead(
        visit_type=visit.visit_type,
        location=visit.location,
        started_at=visit.started_at,
        ended_at=visit.ended_at,
        attending_provider_id=visit.attending_provider_id,
        updated_at=visit.updated_at,
    )


def update_visit_reason(
    session: Session,
    visit_id: int,
    *,
    data: VisitReasonPanelUpdate,
    actor_id: Optional[int],
    context: Optional[dict] = None,
) -> VisitReasonPanelRead:
    visit = _get_visit(session, visit_id)
    visit.reason = data.reason

    audit.record_event(
        session,
        actor_id=actor_id,
        action="visit.update.reason",
        resource_type="visit",
        resource_id=str(visit.id),
        metadata=_visit_metadata(visit, panel="reason"),
        context=context or {},
    )

    session.commit()
    session.refresh(visit)

    return VisitReasonPanelRead(reason=visit.reason, updated_at=visit.updated_at)


def _update_visit_text_panel(
    session: Session,
    visit_id: int,
    *,
    panel: str,
    note_type: str,
    data: VisitNarrativePanelUpdate,
    actor_id: Optional[int],
    context: Optional[dict] = None,
) -> VisitNarrativePanelRead:
    visit = _get_visit(session, visit_id)
    note = _upsert_note(
        session,
        visit,
        note_type=note_type,
        content=data.content,
        actor_id=actor_id,
    )

    audit.record_event(
        session,
        actor_id=actor_id,
        action=f"visit.update.{panel}",
        resource_type="visit",
        resource_id=str(visit.id),
        metadata=_visit_metadata(visit, panel=panel),
        context=context or {},
    )

    session.commit()
    session.refresh(note)

    return _build_text_panel(note)


def update_visit_anamnesis(
    session: Session,
    visit_id: int,
    *,
    data: VisitNarrativePanelUpdate,
    actor_id: Optional[int],
    context: Optional[dict] = None,
) -> VisitNarrativePanelRead:
    return _update_visit_text_panel(
        session,
        visit_id,
        panel="anamnesis",
        note_type="visit.anamnesis",
        data=data,
        actor_id=actor_id,
        context=context,
    )


def update_visit_status(
    session: Session,
    visit_id: int,
    *,
    data: VisitNarrativePanelUpdate,
    actor_id: Optional[int],
    context: Optional[dict] = None,
) -> VisitNarrativePanelRead:
    return _update_visit_text_panel(
        session,
        visit_id,
        panel="status",
        note_type="visit.status",
        data=data,
        actor_id=actor_id,
        context=context,
    )


def update_visit_summary(
    session: Session,
    visit_id: int,
    *,
    data: VisitNarrativePanelUpdate,
    actor_id: Optional[int],
    context: Optional[dict] = None,
) -> VisitSummaryPanelRead:
    panel = _update_visit_text_panel(
        session,
        visit_id,
        panel="summary",
        note_type="visit.summary",
        data=data,
        actor_id=actor_id,
        context=context,
    )
    return VisitSummaryPanelRead(**panel.model_dump())


def update_visit_diagnoses(
    session: Session,
    visit_id: int,
    *,
    data: VisitDiagnosesPanelUpdate,
    actor_id: Optional[int],
    context: Optional[dict] = None,
) -> VisitDiagnosesPanelRead:
    visit = _get_visit(session, visit_id)
    note = _upsert_diagnoses(session, visit, data, actor_id)

    audit.record_event(
        session,
        actor_id=actor_id,
        action="visit.update.diagnoses",
        resource_type="visit",
        resource_id=str(visit.id),
        metadata=_visit_metadata(visit, panel="diagnoses"),
        context=context or {},
    )

    session.commit()
    session.refresh(note)
    return _build_diagnoses_panel(note)


def update_visit_orders(
    session: Session,
    visit_id: int,
    *,
    data: VisitOrdersPanelUpdate,
    actor_id: Optional[int],
    context: Optional[dict] = None,
) -> VisitOrdersPanelRead:
    visit = _get_visit(session, visit_id)
    _replace_orders(session, visit, data.orders, actor_id)

    audit.record_event(
        session,
        actor_id=actor_id,
        action="visit.update.orders",
        resource_type="visit",
        resource_id=str(visit.id),
        metadata=_visit_metadata(visit, panel="orders"),
        context=context or {},
    )

    session.commit()
    return _build_orders_panel(session, visit.id)
