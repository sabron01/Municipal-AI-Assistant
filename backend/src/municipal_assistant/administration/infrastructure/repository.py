from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from ..domain.entities import Category, Direction, Service
from ..domain.errors import CatalogConflict, CatalogEntryNotFound
from .models import CatalogAuditRow, CategoryRow, DirectionRow, ServiceRow


class SqlAlchemyCatalogRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    @staticmethod
    def _direction(row: DirectionRow) -> Direction:
        return Direction(row.id, row.name, row.created_at)

    @staticmethod
    def _service(row: ServiceRow, direction_name: str) -> Service:
        return Service(row.id, row.direction_id, direction_name, row.name, row.created_at)

    @staticmethod
    def _category(row: CategoryRow, parent_name: str | None) -> Category:
        return Category(row.id, row.parent_id, parent_name, row.name, row.created_at,
            retention_years=row.retention_years)

    @staticmethod
    def _record_audit(session, *, actor_id: UUID, entity_type: str, entity_id: UUID, action: str) -> None:
        session.add(CatalogAuditRow(actor_id=actor_id, entity_type=entity_type,
            entity_id=entity_id, action=action))

    def get_direction(self, direction_id: UUID) -> Direction | None:
        with self.session_factory() as session:
            row = session.get(DirectionRow, direction_id)
            return self._direction(row) if row else None

    def list_directions(self) -> list[Direction]:
        with self.session_factory() as session:
            rows = session.scalars(select(DirectionRow).order_by(DirectionRow.name, DirectionRow.id))
            return [self._direction(row) for row in rows]

    def create_direction(self, *, name: str, normalized_name: str, actor_id: UUID) -> Direction:
        with self.session_factory() as session:
            row = DirectionRow(id=uuid4(), name=name, normalized_name=normalized_name, created_by=actor_id)
            session.add(row)
            try:
                session.flush()
                self._record_audit(session, actor_id=actor_id, entity_type="direction",
                    entity_id=row.id, action="catalog.direction_created")
                session.commit()
                session.refresh(row)
            except IntegrityError as exc:
                session.rollback()
                raise CatalogConflict("A direction with this name already exists") from exc
            return self._direction(row)

    def rename_direction(self, direction_id: UUID, *, name: str, normalized_name: str,
                         actor_id: UUID) -> Direction:
        with self.session_factory() as session:
            row = session.scalar(select(DirectionRow).where(DirectionRow.id == direction_id).with_for_update())
            if row is None:
                raise CatalogEntryNotFound("Direction was not found")
            row.name, row.normalized_name = name, normalized_name
            try:
                session.flush()
                self._record_audit(session, actor_id=actor_id, entity_type="direction",
                    entity_id=row.id, action="catalog.direction_renamed")
                session.commit()
                session.refresh(row)
            except IntegrityError as exc:
                session.rollback()
                raise CatalogConflict("A direction with this name already exists") from exc
            return self._direction(row)

    def get_service(self, service_id: UUID) -> Service | None:
        with self.session_factory() as session:
            result = session.execute(select(ServiceRow, DirectionRow.name).join(
                DirectionRow, DirectionRow.id == ServiceRow.direction_id).where(ServiceRow.id == service_id)).first()
            return self._service(result[0], result[1]) if result else None

    def list_services(self, *, direction_id: UUID | None = None) -> list[Service]:
        statement = select(ServiceRow, DirectionRow.name).join(
            DirectionRow, DirectionRow.id == ServiceRow.direction_id)
        if direction_id is not None:
            statement = statement.where(ServiceRow.direction_id == direction_id)
        statement = statement.order_by(DirectionRow.name, ServiceRow.name, ServiceRow.id)
        with self.session_factory() as session:
            return [self._service(row, direction_name)
                    for row, direction_name in session.execute(statement)]

    def create_service(self, *, direction_id: UUID, name: str, normalized_name: str,
                       actor_id: UUID) -> Service:
        with self.session_factory() as session:
            direction = session.get(DirectionRow, direction_id)
            if direction is None:
                raise CatalogEntryNotFound("Direction was not found")
            row = ServiceRow(id=uuid4(), direction_id=direction_id, name=name,
                normalized_name=normalized_name, created_by=actor_id)
            session.add(row)
            try:
                session.flush()
                self._record_audit(session, actor_id=actor_id, entity_type="service",
                    entity_id=row.id, action="catalog.service_created")
                direction_name = direction.name
                session.commit()
                session.refresh(row)
            except IntegrityError as exc:
                session.rollback()
                raise CatalogConflict("A service with this name already exists in the direction") from exc
            return self._service(row, direction_name)

    def rename_service(self, service_id: UUID, *, name: str, normalized_name: str,
                       actor_id: UUID) -> Service:
        with self.session_factory() as session:
            row = session.scalar(select(ServiceRow).where(ServiceRow.id == service_id).with_for_update())
            if row is None:
                raise CatalogEntryNotFound("Service was not found")
            row.name, row.normalized_name = name, normalized_name
            direction_name = session.scalar(select(DirectionRow.name).where(
                DirectionRow.id == row.direction_id))
            try:
                session.flush()
                self._record_audit(session, actor_id=actor_id, entity_type="service",
                    entity_id=row.id, action="catalog.service_renamed")
                session.commit()
                session.refresh(row)
            except IntegrityError as exc:
                session.rollback()
                raise CatalogConflict("A service with this name already exists in the direction") from exc
            return self._service(row, direction_name)

    def service_exists(self, service_id: UUID) -> bool:
        with self.session_factory() as session:
            return session.scalar(select(ServiceRow.id).where(ServiceRow.id == service_id).limit(1)) is not None

    def get_category(self, category_id: UUID) -> Category | None:
        parent = aliased(CategoryRow)
        with self.session_factory() as session:
            result = session.execute(select(CategoryRow, parent.name).outerjoin(
                parent, parent.id == CategoryRow.parent_id).where(CategoryRow.id == category_id)).first()
            return self._category(result[0], result[1]) if result else None

    def list_categories(self, *, parent_id: UUID | None = None,
                        filter_by_parent: bool = False) -> list[Category]:
        parent = aliased(CategoryRow)
        statement = select(CategoryRow, parent.name).outerjoin(parent, parent.id == CategoryRow.parent_id)
        if filter_by_parent:
            statement = statement.where(CategoryRow.parent_id == parent_id)
        statement = statement.order_by(CategoryRow.name, CategoryRow.id)
        with self.session_factory() as session:
            return [self._category(row, parent_name)
                    for row, parent_name in session.execute(statement)]

    def create_category(self, *, parent_id: UUID | None, name: str, normalized_name: str,
                        actor_id: UUID, retention_years: int | None = None) -> Category:
        with self.session_factory() as session:
            parent_name = None
            if parent_id is not None:
                parent = session.get(CategoryRow, parent_id)
                if parent is None:
                    raise CatalogEntryNotFound("Parent category was not found")
                parent_name = parent.name
            row = CategoryRow(id=uuid4(), parent_id=parent_id, name=name,
                normalized_name=normalized_name, created_by=actor_id,
                retention_years=retention_years)
            session.add(row)
            try:
                session.flush()
                self._record_audit(session, actor_id=actor_id, entity_type="category",
                    entity_id=row.id, action="catalog.category_created")
                session.commit()
                session.refresh(row)
            except IntegrityError as exc:
                session.rollback()
                raise CatalogConflict("A category with this name already exists at this level") from exc
            return self._category(row, parent_name)

    def rename_category(self, category_id: UUID, *, name: str, normalized_name: str,
                        actor_id: UUID, retention_years: int | None = None,
                        update_retention: bool = False) -> Category:
        parent = aliased(CategoryRow)
        with self.session_factory() as session:
            result = session.execute(select(CategoryRow, parent.name).outerjoin(
                parent, parent.id == CategoryRow.parent_id).where(
                CategoryRow.id == category_id).with_for_update(of=CategoryRow)).first()
            if result is None:
                raise CatalogEntryNotFound("Category was not found")
            row, parent_name = result
            row.name, row.normalized_name = name, normalized_name
            if update_retention:
                row.retention_years = retention_years
            try:
                session.flush()
                self._record_audit(session, actor_id=actor_id, entity_type="category",
                    entity_id=row.id, action="catalog.category_renamed")
                session.commit()
                session.refresh(row)
            except IntegrityError as exc:
                session.rollback()
                raise CatalogConflict("A category with this name already exists at this level") from exc
            return self._category(row, parent_name)

    def category_exists(self, category_id: UUID) -> bool:
        with self.session_factory() as session:
            return session.scalar(select(CategoryRow.id).where(CategoryRow.id == category_id).limit(1)) is not None
