from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from municipal_assistant.administration.application.use_cases import CatalogUseCases
from municipal_assistant.administration.domain.errors import CatalogConflict
from municipal_assistant.administration.infrastructure.models import (
    CatalogAuditRow,
    CategoryRow,
    DirectionRow,
    ServiceRow,
)
from municipal_assistant.administration.infrastructure.repository import SqlAlchemyCatalogRepository
from municipal_assistant.documents.infrastructure.sqlalchemy_models import Base


@pytest.fixture
def catalog():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        execution_options={"schema_translate_map": {"administration": None}},
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    tables = [DirectionRow.__table__, ServiceRow.__table__, CategoryRow.__table__,
              CatalogAuditRow.__table__]
    Base.metadata.create_all(engine, tables=tables)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    use_cases = CatalogUseCases(SqlAlchemyCatalogRepository(sessions))
    try:
        yield use_cases, sessions
    finally:
        # The database is private in-memory state for this fixture; disposing it
        # is sufficient and avoids SQLite's restriction on dropping populated
        # self-referencing category tables while FK enforcement is enabled.
        engine.dispose()


def test_catalog_hierarchies_are_persisted_and_operations_audited(catalog):
    use_cases, sessions = catalog
    actor_id = uuid4()
    direction = use_cases.create_direction(name="Finances", actor_id=actor_id)
    service = use_cases.create_service(direction_id=direction.id, name="Budget", actor_id=actor_id)
    root = use_cases.create_category(parent_id=None, name="Records", actor_id=actor_id)
    child = use_cases.create_category(parent_id=root.id, name="Invoices", actor_id=actor_id)

    assert use_cases.list_services(direction_id=direction.id) == [service]
    assert use_cases.list_categories(parent_id=root.id, filter_by_parent=True) == [child]
    assert use_cases.service_exists(service.id)
    assert use_cases.category_exists(child.id)

    with sessions() as session:
        audit_count = session.scalar(select(func.count()).select_from(CatalogAuditRow))
    assert audit_count == 4


def test_catalog_rejects_duplicate_names_after_normalization(catalog):
    use_cases, _sessions = catalog
    actor_id = uuid4()
    direction = use_cases.create_direction(name="  Finance  ", actor_id=actor_id)

    with pytest.raises(CatalogConflict):
        use_cases.create_direction(name="FINANCE", actor_id=actor_id)

    assert use_cases.list_directions() == [direction]
