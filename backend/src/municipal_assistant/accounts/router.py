from datetime import datetime
from html import escape
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, Header, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field

from .email import EmailDeliveryUnavailable
from .models import AccountRow
from .security import digest_secret, secure_equal
from .service import (AccountConflict, AccountNotFound, AccountService, InvalidAccountToken,
                      PERMISSIONS)

router = APIRouter(tags=["accounts"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AccountCreateIn(BaseModel):
    email: EmailStr


class PermissionsIn(BaseModel):
    permissions: list[str]


def _service(request: Request) -> AccountService:
    service = getattr(request.app.state, "account_service", None)
    if service is None or not service.settings.auth_enabled:
        raise HTTPException(503, "Account services are not configured")
    return service


def _current(request: Request):
    service = _service(request)
    pair = service.current_session(request.cookies.get(service.settings.session_cookie_name))
    if pair is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return pair


def _require_csrf(request: Request, csrf_header: str | None) -> None:
    settings = _service(request).settings
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
    pair = _current(request)
    if (not csrf_cookie or not csrf_header or not secure_equal(csrf_cookie, csrf_header)
            or not secure_equal(digest_secret(csrf_cookie), pair[1].csrf_hash)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF validation failed")


def _require_admin(request: Request, csrf_header: str | None = None):
    account, session = _current(request)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        _require_csrf(request, csrf_header)
    if not account.is_central_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Central administrator permission required")
    return account


def _account_out(account: AccountRow) -> dict:
    return {"id": account.id, "email": account.email, "status": account.status,
            "is_central_admin": account.is_central_admin, "created_at": account.created_at}


@router.post("/auth/login")
def login(payload: LoginIn, request: Request, response: Response):
    result = _service(request).authenticate(payload.email, payload.password,
        request.client.host if request.client else "unknown")
    if result is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    account, session_token, csrf_token = result
    settings = _service(request).settings
    max_age = max(3600, settings.session_ttl_hours * 3600)
    response.set_cookie(settings.session_cookie_name, session_token, max_age=max_age, httponly=True,
        secure=settings.cookie_secure, samesite="strict", path="/")
    response.set_cookie(settings.csrf_cookie_name, csrf_token, max_age=max_age, httponly=False,
        secure=settings.cookie_secure, samesite="strict", path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"id": account.id, "email": account.email, "is_central_admin": account.is_central_admin,
            "csrf_token": csrf_token}


@router.get("/auth/me")
def me(request: Request, response: Response):
    account, _session = _current(request)
    response.headers["Cache-Control"] = "no-store"
    return {"id": account.id, "email": account.email, "is_central_admin": account.is_central_admin,
            }


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response,
           csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    _require_csrf(request, csrf_header)
    service = _service(request)
    service.logout(request.cookies[service.settings.session_cookie_name])
    response.delete_cookie(service.settings.session_cookie_name, path="/", secure=service.settings.cookie_secure,
                           httponly=True, samesite="strict")
    response.delete_cookie(service.settings.csrf_cookie_name, path="/", secure=service.settings.cookie_secure,
                           samesite="strict")


@router.get("/auth/activate", response_class=HTMLResponse)
def activate_form(token: str):
    safe_token = escape(token, quote=True)
    return HTMLResponse(f"""<!doctype html><meta charset="utf-8"><title>Activer le compte</title>
<meta name="referrer" content="no-referrer"><h1>Activer le compte</h1>
<form method="post" action="/api/v1/auth/activate"><input type="hidden" name="token" value="{safe_token}">
<label>Nouveau mot de passe <input type="password" name="password" minlength="15" maxlength="128" required></label>
<button type="submit">Activer</button></form>""", headers={"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})


@router.post("/auth/activate")
def activate(token: Annotated[str, Form(min_length=32, max_length=128)],
             password: Annotated[str, Form(min_length=15, max_length=128)], request: Request):
    try:
        _service(request).activate(token, password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except InvalidAccountToken as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"status": "activated"}


@router.get("/auth/reset-password", response_class=HTMLResponse)
def reset_password_form(token: str):
    safe_token = escape(token, quote=True)
    return HTMLResponse(f"""<!doctype html><meta charset="utf-8"><title>Réinitialiser le mot de passe</title>
<meta name="referrer" content="no-referrer"><h1>Réinitialiser le mot de passe</h1>
<form method="post" action="/api/v1/auth/reset-password"><input type="hidden" name="token" value="{safe_token}">
<label>Nouveau mot de passe <input type="password" name="password" minlength="15" maxlength="128" required></label>
<button type="submit">Réinitialiser</button></form>""", headers={"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})


@router.post("/auth/reset-password")
def reset_password(token: Annotated[str, Form(min_length=32, max_length=128)],
                   password: Annotated[str, Form(min_length=15, max_length=128)], request: Request):
    try:
        _service(request).reset_password(token, password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except InvalidAccountToken as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"status": "password_reset"}


@router.get("/admin/accounts")
def list_accounts(request: Request):
    _require_admin(request)
    return [_account_out(row) for row in _service(request).list_accounts()]


@router.post("/admin/accounts", status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreateIn, request: Request,
                   csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    admin = _require_admin(request, csrf_header)
    try:
        return _account_out(_service(request).create_account(admin.id, str(payload.email)))
    except AccountConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except EmailDeliveryUnavailable as exc:
        raise HTTPException(503, "Account created pending; email delivery is unavailable") from exc


@router.post("/admin/accounts/{account_id}/activation")
def resend_activation(account_id: UUID, request: Request,
                      csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    admin = _require_admin(request, csrf_header)
    try:
        _service(request).resend_activation(admin.id, account_id)
    except AccountNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except EmailDeliveryUnavailable as exc:
        raise HTTPException(503, "Email delivery is unavailable") from exc
    return {"status": "activation_sent"}


@router.post("/admin/accounts/{account_id}/password-reset")
def request_reset(account_id: UUID, request: Request,
                  csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    admin = _require_admin(request, csrf_header)
    try:
        _service(request).request_password_reset(admin.id, account_id)
    except AccountNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except EmailDeliveryUnavailable as exc:
        raise HTTPException(503, "Email delivery is unavailable") from exc
    return {"status": "reset_sent"}


@router.post("/admin/accounts/{account_id}/disable")
def disable_account(account_id: UUID, request: Request,
                    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    admin = _require_admin(request, csrf_header)
    try:
        return _account_out(_service(request).set_account_status(admin.id, account_id, "disabled"))
    except (AccountConflict, AccountNotFound) as exc:
        raise HTTPException(409 if isinstance(exc, AccountConflict) else 404, str(exc)) from exc


@router.post("/admin/accounts/{account_id}/reactivate")
def reactivate_account(account_id: UUID, request: Request,
                       csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    admin = _require_admin(request, csrf_header)
    try:
        return _account_out(_service(request).set_account_status(admin.id, account_id, "active"))
    except (AccountConflict, AccountNotFound) as exc:
        raise HTTPException(409 if isinstance(exc, AccountConflict) else 404, str(exc)) from exc


@router.put("/admin/accounts/{account_id}/central-admin")
def promote_admin(account_id: UUID, request: Request,
                  csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    admin = _require_admin(request, csrf_header)
    try:
        return _account_out(_service(request).set_central_admin(admin.id, account_id, True))
    except AccountNotFound as exc:
        raise HTTPException(404, str(exc)) from exc


@router.delete("/admin/accounts/{account_id}/central-admin")
def revoke_admin(account_id: UUID, request: Request,
                 csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    admin = _require_admin(request, csrf_header)
    try:
        return _account_out(_service(request).set_central_admin(admin.id, account_id, False))
    except (AccountConflict, AccountNotFound) as exc:
        raise HTTPException(409 if isinstance(exc, AccountConflict) else 404, str(exc)) from exc


@router.put("/admin/accounts/{account_id}/services/{service_id}/permissions")
def set_permissions(account_id: UUID, service_id: UUID, payload: PermissionsIn, request: Request,
                    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None):
    admin = _require_admin(request, csrf_header)
    if len(payload.permissions) != len(set(payload.permissions)) or not set(payload.permissions).issubset(PERMISSIONS):
        raise HTTPException(422, "Unsupported or duplicate permission")
    try:
        _service(request).replace_permissions(admin.id, account_id, service_id, set(payload.permissions))
    except AccountNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"account_id": account_id, "service_id": service_id,
            "permissions": sorted(payload.permissions)}


@router.get("/admin/accounts/{account_id}/permissions")
def list_permissions(account_id: UUID, request: Request):
    _require_admin(request)
    try:
        _service(request).get_account(account_id)
    except AccountNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"account_id": account_id,
            "services": _service(request).permissions_by_service(account_id)}
