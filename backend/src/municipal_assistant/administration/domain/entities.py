from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Direction:
    id: UUID
    name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Service:
    id: UUID
    direction_id: UUID
    direction_name: str
    name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Category:
    id: UUID
    parent_id: UUID | None
    parent_name: str | None
    name: str
    created_at: datetime
    retention_years: int | None = field(default=None, kw_only=True)
