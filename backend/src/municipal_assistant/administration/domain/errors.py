class CatalogError(Exception):
    """Base error for Administration catalog operations."""


class CatalogEntryNotFound(CatalogError):
    pass


class CatalogConflict(CatalogError):
    pass


class InvalidCatalogEntry(CatalogError):
    pass
