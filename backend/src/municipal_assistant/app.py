import logging
from uuid import uuid4
from tempfile import SpooledTemporaryFile
from inspect import isawaitable, iscoroutinefunction
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .documents.domain.errors import (AccessPolicyUnavailable, ConcurrentModification, DependencyUnavailable,
    DocumentError,
    DocumentDeleted, DocumentNotFound, InvalidDocument, InvalidPageCursor, InvalidUpload,
    ReferenceConflict, UnsupportedMediaType, UploadTooLarge)
from .documents.presentation.router import router as documents_router
from .accounts.composition import build_account_service
from .accounts.router import router as accounts_router
from .accounts.settings import AccountSettings
from .accounts.service import DatabaseDocumentAccessPolicy
from .administration.composition import build_catalog_service
from .administration.presentation.router import router as administration_router
from .documents.infrastructure.activation import build_configured_document_service
from .documents.infrastructure.settings import DocumentSettings

logger = logging.getLogger(__name__)


class UploadBodyLimitMiddleware:
    """Bounds multipart request buffering before FastAPI parses an UploadFile."""
    def __init__(self, app: ASGIApp, *, memory_spool_bytes: int = 1024 * 1024):
        self.app, self.memory_spool_bytes = app, memory_spool_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if (scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}
                or not scope.get("path", "").startswith("/api/v1/documents")):
            return await self.app(scope, receive, send)
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        is_multipart = headers.get(b"content-type", b"").lower().startswith(b"multipart/form-data")
        state = scope.get("app").state if scope.get("app") else None
        max_upload_bytes = getattr(state, "max_upload_bytes", None)
        request_id = str(uuid4())
        resolver = getattr(state, "actor_resolver", None)
        if is_multipart and not max_upload_bytes:
            response = JSONResponse(status_code=503, media_type="application/problem+json", content={
                "type": "about:blank", "title": "Upload disabled", "status": 503,
                "detail": "Upload size and file type policies are not configured.", "request_id": request_id})
            return await response(scope, receive, send)
        try:
            trusted_actor = resolver(Request(scope, receive=receive))
            if isawaitable(trusted_actor):
                trusted_actor = await trusted_actor
            from uuid import UUID
            if not isinstance(trusted_actor, UUID):
                raise ValueError("No trusted actor")
            scope.setdefault("state", {})["trusted_actor_id"] = trusted_actor
        except Exception:
            response = JSONResponse(status_code=503, media_type="application/problem+json", content={
                "type": "about:blank", "title": "Access policy unavailable", "status": 503,
                "detail": "A trusted identity could not be established.", "request_id": request_id})
            return await response(scope, receive, send)
        max_body = max_upload_bytes + 64 * 1024 if is_multipart else 16 * 1024
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = 0
        if declared > max_body:
            response = JSONResponse(status_code=413, media_type="application/problem+json", content={
                "type": "about:blank", "title": "Content Too Large", "status": 413,
                "detail": "Multipart request exceeds the configured size limit.", "request_id": request_id})
            return await response(scope, receive, send)
        body = SpooledTemporaryFile(max_size=self.memory_spool_bytes, mode="w+b")
        size = 0
        try:
            more = True
            while more:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > max_body:
                    response = JSONResponse(status_code=413, media_type="application/problem+json", content={
                        "type": "about:blank", "title": "Content Too Large", "status": 413,
                        "detail": "Multipart request exceeds the configured size limit.", "request_id": request_id})
                    return await response(scope, receive, send)
                body.write(chunk)
                more = message.get("more_body", False)
            body.seek(0)
            async def replay():
                chunk = body.read(64 * 1024)
                if chunk:
                    return {"type": "http.request", "body": chunk, "more_body": body.tell() < size}
                return await receive()
            return await self.app(scope, replay, send)
        finally:
            body.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Municipal AI Assistant API", version="1.0.0")
    account_settings = AccountSettings.from_environment()
    account_service, account_engine = build_account_service(account_settings)
    app.state.account_service = account_service
    app.state.account_engine = account_engine
    app.state.catalog_service = build_catalog_service(account_engine) if account_engine else None
    app.state.document_service = None
    def resolve_actor(request: Request):
        service = getattr(request.app.state, "account_service", None)
        if service is None or not service.settings.auth_enabled:
            raise AccessPolicyUnavailable("Authentication is not configured")
        pair = service.current_session(request.cookies.get(service.settings.session_cookie_name))
        if pair is None:
            raise AccessPolicyUnavailable("A trusted identity could not be established")
        return pair[0].id
    app.state.actor_resolver = resolve_actor
    app.state.max_upload_bytes = None
    app.add_middleware(UploadBodyLimitMiddleware)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        if request.url.path.startswith("/api/v1"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok"}

    async def render_problem(request: Request, status_code: int, title: str, detail: str):
        return JSONResponse(status_code=status_code, media_type="application/problem+json", content={
            "type": "about:blank", "title": title, "status": status_code, "detail": detail,
            "instance": str(request.url.path), "request_id": getattr(request.state, "request_id", None),
        })

    @app.exception_handler(DocumentError)
    async def domain_problem_handler(request: Request, exc: DocumentError):
        status_code, title, detail = 500, "Internal Server Error", "The request could not be completed."
        if isinstance(exc, AccessPolicyUnavailable): status_code, title, detail = 503, "Access policy unavailable", str(exc)
        elif isinstance(exc, DependencyUnavailable): status_code, title, detail = 503, "Dependency unavailable", str(exc)
        elif isinstance(exc, DocumentNotFound | DocumentDeleted): status_code, title, detail = 404, "Not Found", "Document was not found."
        elif isinstance(exc, ConcurrentModification): status_code, title, detail = 412, "Precondition Failed", str(exc)
        elif isinstance(exc, ReferenceConflict): status_code, title, detail = 409, "Conflict", str(exc) or "A document with this reference number already exists."
        elif isinstance(exc, UploadTooLarge): status_code, title, detail = 413, "Content Too Large", str(exc)
        elif isinstance(exc, UnsupportedMediaType): status_code, title, detail = 415, "Unsupported Media Type", str(exc)
        elif isinstance(exc, InvalidUpload): status_code, title, detail = 400, "Invalid Upload", str(exc)
        elif isinstance(exc, InvalidDocument): status_code, title, detail = 422, "Invalid Document", str(exc)
        return await render_problem(request, status_code, title, detail)

    @app.exception_handler(HTTPException)
    async def http_problem_handler(request: Request, exc: HTTPException):
        return await render_problem(request, exc.status_code, "Request Error", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_problem_handler(request: Request, exc: RequestValidationError):
        return await render_problem(request, 422, "Validation Error", "Request fields are invalid.")

    @app.exception_handler(Exception)
    async def problem_handler(request: Request, exc: Exception):
        return await render_problem(request, 500, "Internal Server Error", "The request could not be completed.")

    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(accounts_router, prefix="/api/v1")
    app.include_router(administration_router, prefix="/api/v1")
    document_settings = DocumentSettings.from_environment()
    if document_settings.requested and not document_settings.policy_approved:
        logger.warning("Documents settings are present but DOCUMENT_POLICY_APPROVED is false; "
                       "the /documents routes remain closed")
    elif document_settings.requested:
        document_service = build_configured_document_service(document_settings)
        configure_documents(app, service=document_service,
                            actor_resolver=app.state.actor_resolver,
                            business_policy_approved=True)
    return app


def configure_documents(app: FastAPI, *, service, actor_resolver,
                        business_policy_approved: bool = False) -> None:
    """Enable routes only with a trusted identity resolver and explicit policy wiring."""
    validator = getattr(service, "validator", None)
    if validator is None or not validator.allowed_media_types:
        raise ValueError("A configured upload size and non-empty MIME allowlist are required")
    if actor_resolver is None:
        raise ValueError("A trusted authentication adapter is required")
    if app.state.account_service is None or not app.state.account_service.settings.auth_enabled:
        raise ValueError("Application-managed authentication must be enabled first")
    if actor_resolver is not app.state.actor_resolver:
        raise ValueError("Documents must use the application-managed session resolver")
    if not isinstance(getattr(service, "access", None), DatabaseDocumentAccessPolicy):
        raise ValueError("Documents must use the database-backed service permission policy")
    if iscoroutinefunction(actor_resolver):
        raise ValueError("Provide a synchronous trusted actor resolver for this API adapter")
    if not business_policy_approved:
        raise ValueError("Open Documents v1 business/security decisions must be approved before enabling routes")
    app.state.document_service = service
    app.state.actor_resolver = actor_resolver
    app.state.max_upload_bytes = validator.max_bytes


app = create_app()
