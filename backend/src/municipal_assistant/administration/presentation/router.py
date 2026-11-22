from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status

from ...accounts.security import digest_secret, secure_equal
from ..application.use_cases import CatalogUseCases
from ..domain.errors import CatalogConflict, CatalogEntryNotFound, InvalidCatalogEntry
from .schemas import (CategoryCreateIn, CategoryOut, DirectionOut, NameIn,
                      ServiceCreateIn, ServiceOut)

router = APIRouter(prefix="/admin/catalog", tags=["administration-catalog"])


def _admin(request: Request, csrf_header: str | None = None):
    accounts = getattr(request.app.state, "account_service", None)
    if accounts is None or not accounts.settings.auth_enabled:
        raise HTTPException(503, "Account services are not configured")
    pair = accounts.current_session(request.cookies.get(accounts.settings.session_cookie_name))
    if pair is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        settings = accounts.settings
        csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
        if (not csrf_cookie or not csrf_header or not secure_equal(csrf_cookie, csrf_header)
                or not secure_equal(digest_secret(csrf_cookie), pair[1].csrf_hash)):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF validation failed")
    if not pair[0].is_central_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Central administrator permission required")
    return pair[0]


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
            name=payload.name, actor_id=actor.id)
    except (CatalogConflict, CatalogEntryNotFound, InvalidCatalogEntry) as exc:
        raise _translate(exc) from exc


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def rename_category(category_id: UUID, payload: NameIn, request: Request,
                    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    actor = _admin(request, csrf_header)
    try:
        return _catalog(request).rename_category(category_id, name=payload.name, actor_id=actor.id)
    except (CatalogConflict, CatalogEntryNotFound, InvalidCatalogEntry) as exc:
        raise _translate(exc) from exc
