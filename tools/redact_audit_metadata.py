from __future__ import annotations

import argparse
from typing import Any, Dict, Tuple

from sqlalchemy import select
from sqlmodel import Session

from app.db.session import engine
from app.models import AuditEvent
from app.services.audit_policy import (
    HETU_PATTERN,
    hash_identifier,
    make_patient_reference,
    sanitize_metadata,
)


def _normalize_metadata(event: AuditEvent) -> Tuple[Dict[str, Any], bool]:
    metadata = dict(event.metadata_json or {})
    changed = False

    if "identifier" in metadata:
        identifier = metadata.pop("identifier")
        if identifier:
            metadata["identifier_token"] = hash_identifier(str(identifier))
        changed = True

    if "patient_id" in metadata:
        patient_id = metadata.pop("patient_id")
        if patient_id is not None:
            metadata["patient_ref"] = make_patient_reference(int(patient_id))
        changed = True

    if "source_patient_id" in metadata:
        source_id = metadata.pop("source_patient_id")
        if source_id is not None:
            metadata["source_patient_ref"] = make_patient_reference(int(source_id))
        changed = True

    if "merged_into" in metadata:
        merged_id = metadata.pop("merged_into")
        if merged_id is not None:
            metadata["merged_into_ref"] = make_patient_reference(int(merged_id))
        changed = True

    for key, value in list(metadata.items()):
        if isinstance(value, str) and HETU_PATTERN.search(value):
            if key == "reason":
                metadata[key] = "[redacted]"
            else:
                metadata[key] = hash_identifier(value)
            changed = True

    return metadata, changed


def redact_events(dry_run: bool = False) -> int:
    updated = 0
    with Session(engine) as session:
        events = session.exec(select(AuditEvent)).all()
        for event in events:
            metadata, changed = _normalize_metadata(event)
            try:
                sanitized = sanitize_metadata(event.resource_type, event.action, metadata)
            except ValueError as exc:
                raise RuntimeError(
                    f"Unable to sanitize audit event {event.id}: {exc}"  # noqa: EM101
                ) from exc

            if changed or sanitized != metadata:
                event.metadata_json = sanitized
                updated += 1

        if dry_run:
            session.rollback()
        else:
            session.commit()
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Redact legacy audit metadata")
    parser.add_argument("--dry-run", action="store_true", help="Do not persist changes")
    args = parser.parse_args()

    updated = redact_events(dry_run=args.dry_run)
    if args.dry_run:
        print(f"[DRY-RUN] Would update {updated} audit events")
    else:
        print(f"Updated {updated} audit events")


if __name__ == "__main__":
    main()
