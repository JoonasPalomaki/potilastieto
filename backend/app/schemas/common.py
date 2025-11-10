from __future__ import annotations

from typing import Generic, Optional, Sequence, TypeVar

from pydantic import BaseModel

T = TypeVar('T')


class Pagination(BaseModel, Generic[T]):
    items: Sequence[T]
    page: int = 1
    page_size: int = 25
    total: int


class MessageResponse(BaseModel):
    detail: str
    code: Optional[str] = None
