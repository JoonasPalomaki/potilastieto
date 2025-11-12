from __future__ import annotations

from hashlib import sha256
import re
from typing import Any, Dict, Optional, Set

from app.core.config import settings

HETU_PATTERN = re.compile(r"\b\d{6}[+\-A]\d{3}[0-9A-Y]\b")

DEFAULT_ALLOWED_KEYS: Set[str] = {"result_count", "index", "page", "page_size"}

RESOURCE_METADATA_KEYS: Dict[str, Set[str]] = {
    "patient": {
        "patient_ref",
        "identifier_token",
        "source_patient_ref",
        "merged_into_ref",
        "reason",
    },
    "appointment": {
        "patient_ref",
        "previous_start",
        "previous_end",
        "reason",
        "notify",
        "auto",
        "provider_id",
        "provider_ids",
        "status",
        "returned",
        "total",
        "start_from",
        "end_to",
        "slot_minutes",
        "groups",
        "slot_count",
        "location",
    },
    "visit": {
        "patient_ref",
        "appointment_id",
        "panel",
    },
}

ACTION_METADATA_KEYS: Dict[str, Set[str]] = {
    "appointment.reschedule": {"previous_start", "previous_end", "reason"},
    "appointment.cancel": {"notify", "reason"},
    "patient.archive": {"reason"},
    "patient.restore": {"reason"},
    "patient.list": {"returned", "total", "search", "status"},
}


def _allowed_keys(resource_type: str, action: str) -> Set[str]:
    allowed = set(DEFAULT_ALLOWED_KEYS)
    allowed.update(RESOURCE_METADATA_KEYS.get(resource_type, set()))
    allowed.update(ACTION_METADATA_KEYS.get(action, set()))
    return allowed


def sanitize_metadata(
    resource_type: str,
    action: str,
    metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not metadata:
        return {}

    allowed = _allowed_keys(resource_type, action)
    sanitized: Dict[str, Any] = {}
    for key, value in metadata.items():
        if key not in allowed:
            raise ValueError(
                f"Audit metadata key '{key}' is not allowed for action '{action}' on '{resource_type}'"
            )
        _ensure_no_hetu(value)
        sanitized[key] = value
    return sanitized


def _ensure_no_hetu(value: Any) -> None:
    if isinstance(value, str):
        if HETU_PATTERN.search(value):
            raise ValueError("Audit metadata may not contain hetu or direct personal identifiers")
    elif isinstance(value, dict):
        for nested in value.values():
            _ensure_no_hetu(nested)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _ensure_no_hetu(item)


def make_patient_reference(patient_id: int) -> str:
    return f"patient:{patient_id}"


def hash_identifier(identifier: str) -> str:
    secret = settings.audit_hash_secret
    digest = sha256(f"{secret}:{identifier}".encode("utf-8")).hexdigest()
    return f"pid:{digest[:16]}"


def ensure_patient_metadata(
    *,
    patient_id: int,
    identifier: Optional[str] = None,
    reason: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {"patient_ref": make_patient_reference(patient_id)}
    if identifier:
        metadata["identifier_token"] = hash_identifier(identifier)
    if reason:
        metadata["reason"] = reason
    if extra:
        metadata.update(extra)
    return metadata


def ensure_appointment_metadata(
    *,
    patient_id: Optional[int] = None,
    reason: Optional[str] = None,
    previous_start: Optional[str] = None,
    previous_end: Optional[str] = None,
    notify: Optional[bool] = None,
    auto: Optional[bool] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    if patient_id is not None:
        metadata["patient_ref"] = make_patient_reference(patient_id)
    if reason is not None:
        metadata["reason"] = reason
    if previous_start is not None:
        metadata["previous_start"] = previous_start
    if previous_end is not None:
        metadata["previous_end"] = previous_end
    if notify is not None:
        metadata["notify"] = notify
    if auto is not None:
        metadata["auto"] = auto
    if extra:
        metadata.update(extra)
    return metadata
