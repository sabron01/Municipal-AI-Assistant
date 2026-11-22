from uuid import uuid4
from tempfile import SpooledTemporaryFile
from inspect import isawaitable, iscoroutinefunction
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .documents.domain.errors import (AccessPolicyUnavailable, ConcurrentModification, DependencyUnavailable,
    DocumentDeleted, DocumentNotFound, InvalidDocument, InvalidPageCursor, InvalidUpload,
    UnsupportedMediaType, UploadTooLarge)
from .documents.presentation.router import router as documents_router


class UploadBodyLimitMiddleware:
    """Bounds multipart request buffering before FastAPI parses an UploadFile."""
    def __init__(self, app: ASGIApp, *, memory_spool_bytes: int = 1024 * 1024):
        self.app, self.memory_spool_bytes = app, memory_spool_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        if not headers.get(b"content-type", b"").lower().startswith(b"multipart/form-data"):
            return await self.app(scope, receive, send)
        state = scope.get("app").state if scope.get("app") else None
        max_upload_bytes = getattr(state, "max_upload_bytes", None)
        request_id = str(uuid4())
        resolver = getattr(state, "actor_resolver", None)
        if not max_upload_bytes or resolver is None:
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
        max_body = max_upload_bytes + 64 * 1024
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
    app.state.document_service = None
    app.state.actor_resolver = None
    app.state.max_upload_bytes = None
    app.add_middleware(UploadBodyLimitMiddleware)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok"}

    @app.exception_handler(Exception)
    async def problem_handler(request: Request, exc: Exception):
        status_code, title, detail = 500, "Internal Server Error", "The request could not be completed."
        if isinstance(exc, HTTPException):
            status_code = exc.status_code
            title = "Request Error"
            detail = str(exc.detail)
        elif isinstance(exc, RequestValidationError):
            status_code, title, detail = 422, "Validation Error", "Request fields are invalid."
        elif isinstance(exc, AccessPolicyUnavailable): status_code, title, detail = 503, "Access policy unavailable", str(exc)
        elif isinstance(exc, DependencyUnavailable): status_code, title, detail = 503, "Dependency unavailable", str(exc)
        elif isinstance(exc, DocumentNotFound | DocumentDeleted): status_code, title, detail = 404, "Not Found", "Document was not found."
        elif isinstance(exc, ConcurrentModification): status_code, title, detail = 412, "Precondition Failed", str(exc)
        elif isinstance(exc, InvalidPageCursor): status_code, title, detail = 400, "Invalid Cursor", str(exc)
        elif isinstance(exc, UploadTooLarge): status_code, title, detail = 413, "Content Too Large", str(exc)
        elif isinstance(exc, UnsupportedMediaType): status_code, title, detail = 415, "Unsupported Media Type", str(exc)
        elif isinstance(exc, InvalidUpload): status_code, title, detail = 400, "Invalid Upload", str(exc)
        elif isinstance(exc, InvalidDocument): status_code, title, detail = 422, "Invalid Document", str(exc)
        return JSONResponse(status_code=status_code, media_type="application/problem+json", content={
            "type": "about:blank", "title": title, "status": status_code, "detail": detail,
            "instance": str(request.url.path), "request_id": getattr(request.state, "request_id", None),
        })

    app.include_router(documents_router, prefix="/api/v1")
    return app


def configure_documents(app: FastAPI, *, service, actor_resolver,
                        business_policy_approved: bool = False) -> None:
    """Enable routes only with a trusted identity resolver and explicit policy wiring."""
    validator = getattr(service, "validator", None)
    if validator is None or not validator.allowed_media_types:
        raise ValueError("A configured upload size and non-empty MIME allowlist are required")
    if actor_resolver is None:
        raise ValueError("A trusted authentication adapter is required")
    if iscoroutinefunction(actor_resolver):
        raise ValueError("Provide a synchronous trusted actor resolver for this API adapter")
    if not business_policy_approved:
        raise ValueError("Open Documents v1 business/security decisions must be approved before enabling routes")
    app.state.document_service = service
    app.state.actor_resolver = actor_resolver
    app.state.max_upload_bytes = validator.max_bytes


app = create_app()
