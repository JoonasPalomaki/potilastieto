from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from io import TextIOBase
from typing import Dict, Iterable, Sequence

from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.models import DiagnosisCode
from . import audit

REQUIRED_HEADERS: Sequence[str] = (
    "code",
    "short_description",
    "long_description",
    "is_deleted",
)
TRUE_VALUES = {"1", "true", "t", "yes", "y", "on", "deleted"}
CODE_NORMALIZE_PATTERN = re.compile(r"[^0-9A-Za-z]+")


@dataclass
class DiagnosisCodeImportResult:
    total_rows: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    marked_deleted: int = 0
    errors: list[str] = field(default_factory=list)


def normalize_code(value: str | None) -> str:
    if not value:
        return ""
    normalized = CODE_NORMALIZE_PATTERN.sub("", value).upper()
    return normalized


def _parse_deleted_flag(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().lower()
    if not normalized:
        return False
    return normalized in TRUE_VALUES


def _ensure_headers(fieldnames: Sequence[str] | None) -> None:
    if not fieldnames:
        raise ValueError("CSV requires a header row with mandated columns")
    normalized = {field.strip().lower() for field in fieldnames if field}
    missing = [header for header in REQUIRED_HEADERS if header not in normalized]
    if missing:
        raise ValueError(
            "CSV missing required columns: " + ", ".join(sorted(missing))
        )


def _normalize_row(row: Dict[str, str | None]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for key, value in row.items():
        if key is None:
            continue
        normalized[key.strip().lower()] = (value or "").strip()
    return normalized


def import_diagnosis_codes(
    session: Session,
    *,
    csv_stream: TextIOBase,
    actor_id: int,
    context: Dict[str, object] | None = None,
    filename: str | None = None,
) -> DiagnosisCodeImportResult:
    reader = csv.DictReader(csv_stream)
    _ensure_headers(reader.fieldnames)

    summary = DiagnosisCodeImportResult()

    for row in reader:
        summary.total_rows += 1
        normalized = _normalize_row(row)
        code_value = normalized.get("code", "")
        if not code_value:
            summary.skipped += 1
            summary.errors.append(f"Row {reader.line_num}: Missing code value")
            continue
        code = code_value.upper()
        normalized_code = normalize_code(code)
        if not normalized_code:
            summary.skipped += 1
            summary.errors.append(
                f"Row {reader.line_num}: Invalid code '{code_value}'"
            )
            continue

        short_description = normalized.get("short_description", "")
        if not short_description:
            summary.skipped += 1
            summary.errors.append(
                f"Row {reader.line_num}: Missing short description for {code}"
            )
            continue

        long_description = normalized.get("long_description") or None
        is_deleted = _parse_deleted_flag(normalized.get("is_deleted"))
        if is_deleted:
            summary.marked_deleted += 1

        existing = session.exec(
            select(DiagnosisCode).where(
                DiagnosisCode.normalized_code == normalized_code
            )
        ).one_or_none()

        if existing is None:
            record = DiagnosisCode(
                code=code,
                normalized_code=normalized_code,
                short_description=short_description,
                long_description=long_description,
                is_deleted=is_deleted,
            )
            session.add(record)
            summary.inserted += 1
        else:
            changed = False
            if existing.code != code:
                existing.code = code
                changed = True
            if existing.short_description != short_description:
                existing.short_description = short_description
                changed = True
            if existing.long_description != long_description:
                existing.long_description = long_description
                changed = True
            if existing.is_deleted != is_deleted:
                existing.is_deleted = is_deleted
                changed = True
            if changed:
                session.add(existing)
                summary.updated += 1

    metadata = {
        "filename": filename,
        "total_rows": summary.total_rows,
        "inserted": summary.inserted,
        "updated": summary.updated,
        "marked_deleted": summary.marked_deleted,
        "skipped": summary.skipped,
        "error_count": len(summary.errors),
    }
    audit.record_event(
        session,
        actor_id=actor_id,
        action="diagnosis_code.import",
        resource_type="diagnosis_code",
        resource_id=None,
        metadata=metadata,
        context=context or {},
    )
    session.commit()
    return summary


def search_diagnosis_codes(
    session: Session,
    *,
    search: str | None = None,
    include_deleted: bool = False,
    page: int = 1,
    page_size: int = 25,
) -> tuple[Iterable[DiagnosisCode], int]:
    safe_page = max(page, 1)
    safe_page_size = max(page_size, 1)

    statement = select(DiagnosisCode)
    count_stmt = select(func.count()).select_from(DiagnosisCode)

    filters = []
    if not include_deleted:
        filters.append(DiagnosisCode.is_deleted.is_(False))

    if search:
        raw = search.strip()
        if raw:
            normalized_search = normalize_code(raw)
            pattern = f"%{raw.lower()}%"
            search_clauses = [
                func.lower(DiagnosisCode.code).like(pattern),
                func.lower(DiagnosisCode.short_description).like(pattern),
                func.lower(func.coalesce(DiagnosisCode.long_description, "")).like(
                    pattern
                ),
            ]
            if normalized_search:
                search_clauses.append(DiagnosisCode.normalized_code == normalized_search)
            filters.append(or_(*search_clauses))

    for filter_ in filters:
        statement = statement.where(filter_)
        count_stmt = count_stmt.where(filter_)

    statement = statement.order_by(DiagnosisCode.code)
    statement = statement.offset((safe_page - 1) * safe_page_size).limit(
        safe_page_size
    )

    items = session.exec(statement).all()
    total = session.exec(count_stmt).one()
    return items, total


__all__ = [
    "DiagnosisCodeImportResult",
    "import_diagnosis_codes",
    "search_diagnosis_codes",
    "normalize_code",
]
