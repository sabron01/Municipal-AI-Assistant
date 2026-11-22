from collections.abc import Iterator
from typing import Annotated
from uuid import UUID
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from ...accounts.security import digest_secret, secure_equal
from ..application.use_cases import CreateDocument
from ..domain.entities import Document
from ..domain.errors import AccessPolicyUnavailable, ConcurrentModification
from ..domain.ports import DocumentQuery
from ..domain.value_objects import CategoryId, DocumentId, ServiceId, VersionId
from .schemas import DocumentCreate, DocumentOut, DocumentPage, DocumentPatch, VersionOut

router = APIRouter(prefix="/documents", tags=["documents"])


def _actor(request: Request) -> UUID:
    resolved = getattr(request.state, "trusted_actor_id", None)
    if isinstance(resolved, UUID):
        return resolved
    resolver = getattr(request.app.state, "actor_resolver", None)
    if resolver is None:
        raise AccessPolicyUnavailable("Identity and access policy have not been configured")
    try:
        actor = resolver(request)
    except Exception as exc:
        raise AccessPolicyUnavailable("A trusted identity could not be established") from exc
    if not isinstance(actor, UUID):
        raise AccessPolicyUnavailable("Configured identity resolver returned no trusted actor")
    return actor


def _require_csrf(request: Request, csrf_header: str | None) -> None:
    accounts = getattr(request.app.state, "account_service", None)
    if accounts is None or not accounts.settings.auth_enabled:
        raise AccessPolicyUnavailable("Application-managed authentication is not configured")
    pair = accounts.current_session(request.cookies.get(accounts.settings.session_cookie_name))
    if pair is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    csrf_cookie = request.cookies.get(accounts.settings.csrf_cookie_name)
    if (not csrf_cookie or not csrf_header or not secure_equal(csrf_cookie, csrf_header)
            or not secure_equal(digest_secret(csrf_cookie), pair[1].csrf_hash)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


def _service(request: Request):
    service = getattr(request.app.state, "document_service", None)
    if service is None:
        raise AccessPolicyUnavailable("Documents module is not configured")
    return service


def _etag(document: Document) -> str:
    return f'"{document.aggregate_version}"'


def _document_out(document: Document) -> DocumentOut:
    return DocumentOut(id=document.id.value, title=document.title, service_id=document.service_id.value,
        category_id=document.category_id.value, current_version_id=document.current_version_id.value,
        status=document.status.value, created_at=document.created_at, updated_at=document.updated_at,
        description=document.description, reference_number=document.reference_number,
        aggregate_version=document.aggregate_version)


def _version_out(version) -> VersionOut:
    return VersionOut(id=version.id.value, sequence=version.sequence,
        original_filename=version.original_filename, detected_mime_type=version.detected_mime_type,
        size_bytes=version.size_bytes, sha256=version.sha256.value, created_at=version.created_at)


def _expected_version(value: str | None) -> int:
    if not value:
        raise HTTPException(status_code=428, detail="If-Match is required")
    try:
        if value.strip().startswith("W/"):
            raise ValueError
        return int(value.strip().strip('"'))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid If-Match header") from exc


def _stream_chunks(readable) -> Iterator[bytes]:
    try:
        while chunk := readable.body.read(64 * 1024):
            yield chunk
    finally:
        readable.close()


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def create_document(request: Request,
                    title: Annotated[str, Form(min_length=1, max_length=300)],
                    service_id: Annotated[UUID, Form()],
                    category_id: Annotated[UUID, Form()],
                    file: Annotated[UploadFile, File()], response: Response,
                    description: Annotated[str | None, Form(max_length=5000)] = None,
                    reference_number: Annotated[str | None, Form(max_length=200)] = None,
                    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    _require_csrf(request, csrf_header)
    form = await request.form()
    allowed_fields = {"title", "service_id", "category_id", "description", "reference_number", "file"}
    if set(form.keys()) - allowed_fields:
        raise HTTPException(status_code=422, detail="Unexpected multipart form field")
    payload = DocumentCreate(title=title, service_id=service_id, category_id=category_id,
        description=description, reference_number=reference_number)
    document = _service(request).create(CreateDocument(payload.title, ServiceId(payload.service_id),
        CategoryId(payload.category_id), file.filename or "upload", file.file, payload.description,
        payload.reference_number), _actor(request))
    response.headers["Location"] = f"{request.url.path}/{document.id.value}"
    response.headers["ETag"] = _etag(document)
    return _document_out(document)


@router.get("", response_model=DocumentPage)
def list_documents(request: Request, service_id: UUID | None = None, category_id: UUID | None = None,
                    cursor: str | None = None, limit: int = Query(default=50, ge=1, le=100)):
    page = _service(request).list(DocumentQuery(ServiceId(service_id) if service_id else None,
        CategoryId(category_id) if category_id else None, cursor, limit), _actor(request))
    return DocumentPage(items=[_document_out(item) for item in page.items], next_cursor=page.next_cursor)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(request: Request, document_id: UUID, response: Response):
    document = _service(request).get(DocumentId(document_id), _actor(request))
    response.headers["ETag"] = _etag(document)
    return _document_out(document)


@router.patch("/{document_id}", response_model=DocumentOut)
def update_document(request: Request, document_id: UUID, payload: DocumentPatch,
                    response: Response, if_match: Annotated[str | None, Header()] = None,
                    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    _require_csrf(request, csrf_header)
    document = _service(request).update(DocumentId(document_id), _actor(request), title=payload.title,
        description=payload.description, reference_number=payload.reference_number,
        service_id=ServiceId(payload.service_id), category_id=CategoryId(payload.category_id),
        expected_version=_expected_version(if_match))
    response.headers["ETag"] = _etag(document)
    return _document_out(document)


@router.post("/{document_id}/versions", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def add_version(request: Request, document_id: UUID, file: Annotated[UploadFile, File()],
                response: Response, if_match: Annotated[str | None, Header()] = None,
                csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    _require_csrf(request, csrf_header)
    document = _service(request).add_version(DocumentId(document_id), file.file, file.filename or "upload",
        _actor(request), _expected_version(if_match))
    response.headers["ETag"] = _etag(document)
    return _document_out(document)


@router.get("/{document_id}/versions", response_model=list[VersionOut])
def list_versions(request: Request, document_id: UUID):
    return [_version_out(item) for item in
            _service(request).versions(DocumentId(document_id), _actor(request))]


@router.get("/{document_id}/content")
def download_document(request: Request, document_id: UUID, version_id: UUID | None = None):
    readable = _service(request).download(DocumentId(document_id), _actor(request),
        VersionId(version_id) if version_id else None)
    filename = quote(readable.filename, safe="")
    return StreamingResponse(_stream_chunks(readable), media_type=readable.content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
                 "Content-Length": str(readable.content_length), "X-Content-Type-Options": "nosniff",
                 "Cache-Control": "private, no-store"}, background=BackgroundTask(readable.close))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(request: Request, document_id: UUID, if_match: Annotated[str | None, Header()] = None,
                    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    _require_csrf(request, csrf_header)
    _service(request).soft_delete(DocumentId(document_id), _actor(request), _expected_version(if_match))
