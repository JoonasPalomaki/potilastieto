from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


class AuditEventRead(BaseModel):
    id: int
    actor_id: Optional[int]
    action: str
    resource_type: str
    resource_id: Optional[str]
    metadata: Dict[str, Any]
    context: Dict[str, Any]
    timestamp: datetime


class AuditQueryParams(BaseModel):
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    actor_id: Optional[int] = None
    action: Optional[str] = None
    from_ts: Optional[datetime] = None
    to_ts: Optional[datetime] = None
