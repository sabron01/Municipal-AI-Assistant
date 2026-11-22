import unicodedata
from uuid import UUID

from ..domain.entities import Category, Direction, Service
from ..domain.errors import CatalogEntryNotFound, InvalidCatalogEntry
from ..domain.ports import CatalogRepository


def normalize_catalog_name(value: str) -> tuple[str, str]:
    display_name = unicodedata.normalize("NFC", value).strip()
    if not display_name or len(display_name) > 200:
        raise InvalidCatalogEntry("Name must contain between 1 and 200 characters")
    if any(unicodedata.category(character).startswith("C") for character in display_name):
        raise InvalidCatalogEntry("Name contains a control character")
    normalized_name = unicodedata.normalize("NFKC", display_name).casefold()
    if len(normalized_name) > 600:
        raise InvalidCatalogEntry("Normalized name is too long")
    return display_name, normalized_name


class CatalogUseCases:
    def __init__(self, repository: CatalogRepository):
        self.repository = repository

    def list_directions(self):
        return self.repository.list_directions()

    def create_direction(self, *, name: str, actor_id: UUID) -> Direction:
        display, normalized = normalize_catalog_name(name)
        return self.repository.create_direction(name=display, normalized_name=normalized, actor_id=actor_id)

    def rename_direction(self, direction_id: UUID, *, name: str, actor_id: UUID) -> Direction:
        display, normalized = normalize_catalog_name(name)
        return self.repository.rename_direction(direction_id, name=display,
            normalized_name=normalized, actor_id=actor_id)

    def list_services(self, *, direction_id: UUID | None = None):
        if direction_id is not None and self.repository.get_direction(direction_id) is None:
            raise CatalogEntryNotFound("Direction was not found")
        return self.repository.list_services(direction_id=direction_id)

    def create_service(self, *, direction_id: UUID, name: str, actor_id: UUID) -> Service:
        if self.repository.get_direction(direction_id) is None:
            raise CatalogEntryNotFound("Direction was not found")
        display, normalized = normalize_catalog_name(name)
        return self.repository.create_service(direction_id=direction_id, name=display,
            normalized_name=normalized, actor_id=actor_id)

    def rename_service(self, service_id: UUID, *, name: str, actor_id: UUID) -> Service:
        display, normalized = normalize_catalog_name(name)
        return self.repository.rename_service(service_id, name=display,
            normalized_name=normalized, actor_id=actor_id)

    def list_categories(self, *, parent_id: UUID | None = None, filter_by_parent: bool = False):
        if filter_by_parent and parent_id is not None:
            parent = self.repository.get_category(parent_id)
            if parent is None:
                raise CatalogEntryNotFound("Parent category was not found")
            if parent.parent_id is not None:
                raise InvalidCatalogEntry("Only top-level categories can have subcategories")
        return self.repository.list_categories(parent_id=parent_id, filter_by_parent=filter_by_parent)

    def create_category(self, *, parent_id: UUID | None, name: str, actor_id: UUID) -> Category:
        if parent_id is not None:
            parent = self.repository.get_category(parent_id)
            if parent is None:
                raise CatalogEntryNotFound("Parent category was not found")
            if parent.parent_id is not None:
                raise InvalidCatalogEntry("Only top-level categories can have subcategories")
        display, normalized = normalize_catalog_name(name)
        return self.repository.create_category(parent_id=parent_id, name=display,
            normalized_name=normalized, actor_id=actor_id)

    def rename_category(self, category_id: UUID, *, name: str, actor_id: UUID) -> Category:
        display, normalized = normalize_catalog_name(name)
        return self.repository.rename_category(category_id, name=display,
            normalized_name=normalized, actor_id=actor_id)

    def service_exists(self, service_id: UUID) -> bool:
        return self.repository.service_exists(service_id)

    def category_exists(self, category_id: UUID) -> bool:
        return self.repository.category_exists(category_id)
