from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NameIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)


class ServiceCreateIn(NameIn):
    direction_id: UUID


class CategoryCreateIn(NameIn):
    parent_id: UUID | None = None
    retention_years: int | None = Field(default=None, ge=1)


class CategoryUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    retention_years: int | None = Field(default=None, ge=1)


class DirectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    created_at: datetime


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    direction_id: UUID
    direction_name: str
    name: str
    created_at: datetime


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    parent_id: UUID | None
    parent_name: str | None
    name: str
    created_at: datetime
    retention_years: int | None
