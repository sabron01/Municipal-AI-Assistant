from sqlalchemy.orm import sessionmaker

from .application.use_cases import CatalogUseCases
from .infrastructure.repository import SqlAlchemyCatalogRepository


def build_catalog_service(engine):
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    return CatalogUseCases(SqlAlchemyCatalogRepository(sessions))
