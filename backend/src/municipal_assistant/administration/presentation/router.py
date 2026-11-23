from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status

from ...accounts.guards import require_central_admin as _admin
from ..application.use_cases import CatalogUseCases
from ..domain.errors import CatalogConflict, CatalogEntryNotFound, InvalidCatalogEntry
from .schemas import (CategoryCreateIn, CategoryOut, CategoryUpdateIn, DirectionOut, NameIn,
                      ServiceCreateIn, ServiceOut)

router = APIRouter(prefix="/admin/catalog", tags=["administration-catalog"])


def _catalog(request: Request) -> CatalogUseCases:
    catalog = getattr(request.app.state, "catalog_service", None)
    if catalog is None:
        raise HTTPException(503, "Administration catalogs are not configured")
    return catalog


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, CatalogEntryNotFound):
        return HTTPException(404, str(exc))
    if isinstance(exc, CatalogConflict):
        return HTTPException(409, str(exc))
    if isinstance(exc, InvalidCatalogEntry):
        return HTTPException(422, str(exc))
    return HTTPException(500, "Catalog operation failed")


@router.get("/directions", response_model=list[DirectionOut])
def list_directions(request: Request):
    _admin(request)
    return _catalog(request).list_directions()


@router.post("/directions", response_model=DirectionOut, status_code=status.HTTP_201_CREATED)
def create_direction(payload: NameIn, request: Request,
                     csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    actor = _admin(request, csrf_header)
    try:
        return _catalog(request).create_direction(name=payload.name, actor_id=actor.id)
    except (CatalogConflict, CatalogEntryNotFound, InvalidCatalogEntry) as exc:
        raise _translate(exc) from exc


@router.patch("/directions/{direction_id}", response_model=DirectionOut)
def rename_direction(direction_id: UUID, payload: NameIn, request: Request,
                     csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    actor = _admin(request, csrf_header)
    try:
        return _catalog(request).rename_direction(direction_id, name=payload.name, actor_id=actor.id)
    except (CatalogConflict, CatalogEntryNotFound, InvalidCatalogEntry) as exc:
        raise _translate(exc) from exc


@router.get("/services", response_model=list[ServiceOut])
def list_services(request: Request, direction_id: UUID | None = None):
    _admin(request)
    try:
        return _catalog(request).list_services(direction_id=direction_id)
    except CatalogEntryNotFound as exc:
        raise _translate(exc) from exc


@router.post("/services", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def create_service(payload: ServiceCreateIn, request: Request,
                   csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    actor = _admin(request, csrf_header)
    try:
        return _catalog(request).create_service(direction_id=payload.direction_id,
            name=payload.name, actor_id=actor.id)
    except (CatalogConflict, CatalogEntryNotFound, InvalidCatalogEntry) as exc:
        raise _translate(exc) from exc


@router.patch("/services/{service_id}", response_model=ServiceOut)
def rename_service(service_id: UUID, payload: NameIn, request: Request,
                   csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    actor = _admin(request, csrf_header)
    try:
        return _catalog(request).rename_service(service_id, name=payload.name, actor_id=actor.id)
    except (CatalogConflict, CatalogEntryNotFound, InvalidCatalogEntry) as exc:
        raise _translate(exc) from exc


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(request: Request, parent_id: UUID | None = None, roots_only: bool = False):
    _admin(request)
    try:
        return _catalog(request).list_categories(parent_id=parent_id,
            filter_by_parent=parent_id is not None or roots_only)
    except (CatalogEntryNotFound, InvalidCatalogEntry) as exc:
        raise _translate(exc) from exc


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreateIn, request: Request,
                    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    actor = _admin(request, csrf_header)
    try:
        return _catalog(request).create_category(parent_id=payload.parent_id,
            name=payload.name, actor_id=actor.id, retention_years=payload.retention_years)
    except (CatalogConflict, CatalogEntryNotFound, InvalidCatalogEntry) as exc:
        raise _translate(exc) from exc


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: UUID, payload: CategoryUpdateIn, request: Request,
                    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    actor = _admin(request, csrf_header)
    try:
        retention_provided = "retention_years" in payload.model_fields_set
        return _catalog(request).update_category(category_id, name=payload.name,
            retention_years=payload.retention_years, update_retention=retention_provided,
            actor_id=actor.id)
    except (CatalogConflict, CatalogEntryNotFound, InvalidCatalogEntry) as exc:
        raise _translate(exc) from exc
