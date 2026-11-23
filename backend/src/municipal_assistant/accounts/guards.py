"""Contrôles d'accès partagés par les routeurs HTTP.

Ce module centralise l'authentification par session, la validation CSRF et
l'exigence d'administrateur central. Les routeurs doivent passer par ces
fonctions plutôt que réimplémenter la logique, afin qu'aucun point d'entrée ne
puisse diverger sur un contrôle de sécurité.
"""
from __future__ import annotations

from fastapi import HTTPException, Request, status

from .models import AccountRow
from .security import digest_secret, secure_equal
from .service import AccountService

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def account_service(request: Request) -> AccountService:
    service = getattr(request.app.state, "account_service", None)
    if service is None or not service.settings.auth_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Account services are not configured")
    return service


def current_account(request: Request):
    service = account_service(request)
    pair = service.current_session(request.cookies.get(service.settings.session_cookie_name))
    if pair is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return pair


def require_csrf(request: Request, csrf_header: str | None) -> None:
    service = account_service(request)
    settings = service.settings
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
    pair = current_account(request)
    if (not csrf_cookie or not csrf_header or not secure_equal(csrf_cookie, csrf_header)
            or not secure_equal(digest_secret(csrf_cookie), pair[1].csrf_hash)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF validation failed")


def require_central_admin(request: Request, csrf_header: str | None = None) -> AccountRow:
    account, _session = current_account(request)
    if request.method not in SAFE_METHODS:
        require_csrf(request, csrf_header)
    if not account.is_central_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Central administrator permission required")
    return account
