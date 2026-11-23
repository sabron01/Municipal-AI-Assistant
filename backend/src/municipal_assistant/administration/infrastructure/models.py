from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ...documents.infrastructure.sqlalchemy_models import Base


class DirectionRow(Base):
    __tablename__ = "directions"
    __table_args__ = (
        Index("uq_directions_normalized_name", "normalized_name", unique=True),
        {"schema": "administration"},
    )

    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(600), nullable=False)
    created_by: Mapped[object] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
        server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now())


class ServiceRow(Base):
    __tablename__ = "services"
    __table_args__ = (
        Index("uq_services_direction_normalized_name", "direction_id", "normalized_name", unique=True),
        Index("ix_services_direction_name", "direction_id", "name"),
        {"schema": "administration"},
    )

    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    direction_id: Mapped[object] = mapped_column(UUID(as_uuid=True), ForeignKey(
        "administration.directions.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(600), nullable=False)
    created_by: Mapped[object] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
        server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now())


class CategoryRow(Base):
    __tablename__ = "categories"
    __table_args__ = (
        Index("uq_categories_root_normalized_name", "normalized_name", unique=True,
              postgresql_where=text("parent_id IS NULL")),
        Index("uq_categories_child_normalized_name", "parent_id", "normalized_name", unique=True,
              postgresql_where=text("parent_id IS NOT NULL")),
        {"schema": "administration"},
    )

    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    parent_id: Mapped[object | None] = mapped_column(UUID(as_uuid=True), ForeignKey(
        "administration.categories.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(600), nullable=False)
    created_by: Mapped[object] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
        server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now())
    retention_years: Mapped[int | None] = mapped_column(Integer)


class CatalogAuditRow(Base):
    __tablename__ = "catalog_audit"
    __table_args__ = ((Index("ix_catalog_audit_created", "created_at")), {"schema": "administration"})

    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_id: Mapped[object] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[object] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
        server_default=func.now())
