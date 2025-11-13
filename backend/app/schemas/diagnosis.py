from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Pagination


class DiagnosisCodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    normalized_code: str
    short_description: str
    long_description: str | None = None
    is_deleted: bool


class DiagnosisCodeSearchResponse(Pagination[DiagnosisCodeRead]):
    pass


class DiagnosisCodeImportSummary(BaseModel):
    total_rows: int
    inserted: int
    updated: int
    marked_deleted: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


class DiagnosisCodeImportResponse(BaseModel):
    filename: str | None = None
    summary: DiagnosisCodeImportSummary
