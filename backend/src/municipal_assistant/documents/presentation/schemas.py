from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    service_id: UUID
    category_id: UUID
    document_date: date
    reference_number: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    issuer: str | None = Field(default=None, max_length=200)
    keywords: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=20)
    confidentiality_level: str | None = Field(default=None, max_length=100)
    retention_code: str | None = Field(default=None, max_length=100)


class DocumentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    service_id: UUID
    category_id: UUID
    document_date: date
    reference_number: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    issuer: str | None = Field(default=None, max_length=200)
    keywords: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=20)
    confidentiality_level: str | None = Field(default=None, max_length=100)
    retention_code: str | None = Field(default=None, max_length=100)


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    sequence: int
    original_filename: str
    detected_mime_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    service_id: UUID
    category_id: UUID
    current_version_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    description: str | None
    reference_number: str | None
    document_date: date
    issuer: str | None
    keywords: list[str]
    confidentiality_level: str | None
    retention_code: str | None
    aggregate_version: int


class DocumentPage(BaseModel):
    items: list[DocumentOut]
    next_cursor: str | None