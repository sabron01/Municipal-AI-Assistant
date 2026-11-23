"""Fixtures for account and authentication integration tests.

A throwaway PostgreSQL database is created for the test session, migrated from
the SQLAlchemy metadata, and dropped afterwards. The source URL is
``TEST_DATABASE_URL`` when provided, otherwise the local ``DATABASE_URL``.
Tests are skipped when no reachable PostgreSQL server is configured.
"""
import os
import re
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from municipal_assistant.accounts.models import (  # noqa: F401 - registers tables
    AccountAuditRow,
    AccountLoginAttemptRow,
    AccountRow,
    AccountSessionRow,
    AccountTokenRow,
    PermissionGrantRow,
)
from municipal_assistant.accounts.service import AccountService
from municipal_assistant.accounts.settings import AccountSettings
from municipal_assistant.documents.infrastructure.sqlalchemy_models import Base

PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "another correct horse battery"
ACCOUNT_TABLES = (
    "accounts.account_login_attempts",
    "accounts.account_audit",
    "accounts.permission_grants",
    "accounts.account_sessions",
    "accounts.account_tokens",
    "accounts.user_accounts",
)


class RecordingMailer:
    def __init__(self):
        self.messages = []

    def send(self, *, recipient: str, subject: str, body: str) -> None:
        self.messages.append(SimpleNamespace(recipient=recipient, subject=subject, body=body))

    def last_token(self) -> str:
        match = re.search(r"[?&]token=([A-Za-z0-9_-]+)", self.messages[-1].body)
        if match is None:
            raise AssertionError("No token found in the last email")
        return match.group(1)


@pytest.fixture(scope="session")
def test_database_url():
    source = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not source:
        pytest.skip("TEST_DATABASE_URL or DATABASE_URL is required for account integration tests")
    url = make_url(source)
    name = f"maa_accounts_it_{uuid4().hex[:12]}"
    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
    except Exception as exc:  # pragma: no cover - environment dependent
        admin_engine.dispose()
        pytest.skip(f"PostgreSQL test database is unavailable: {exc}")

    test_url = url.set(database=name)
    engine = create_engine(test_url)
    with engine.begin() as connection:
        for schema in ("documents", "accounts", "administration"):
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    Base.metadata.create_all(engine)
    try:
        yield test_url
    finally:
        engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin_engine.dispose()


@pytest.fixture(scope="session")
def test_engine(test_database_url):
    engine = create_engine(test_database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(test_engine):
    with test_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {', '.join(ACCOUNT_TABLES)} RESTART IDENTITY CASCADE"))
    return sessionmaker(bind=test_engine, expire_on_commit=False)


@pytest.fixture
def mailer():
    return RecordingMailer()


@pytest.fixture
def make_settings(test_database_url):
    base = AccountSettings(
        database_url=str(test_database_url),
        initial_admin_email=None,
        public_base_url="http://localhost:8000",
        smtp_host="127.0.0.1",
        smtp_port=1025,
        smtp_username=None,
        smtp_password=None,
        smtp_sender="noreply@municipal.local",
        smtp_starttls=False,
        smtp_use_ssl=False,
        smtp_allow_insecure_local=True,
        session_ttl_hours=8,
        cookie_secure=False,
        auth_enabled=True,
        activation_ttl_days=7,
        password_reset_ttl_days=7,
        login_identifier="email",
        mfa_required=False,
    )

    def factory(**overrides):
        return replace(base, **overrides)

    return factory


@pytest.fixture
def build_service(session_factory, make_settings, mailer):
    def factory(**overrides):
        return AccountService(session_factory, make_settings(**overrides), mailer)

    return factory


@pytest.fixture
def service(build_service):
    return build_service()


def create_active_account(service, mailer, email="agent@municipal.tn", *, password=PASSWORD):
    account = service.create_account(uuid4(), email)
    service.activate(mailer.last_token(), password)
    return service.get_account(account.id)


def bootstrap_active_admin(service, mailer, email="admin@municipal.tn"):
    assert service.bootstrap_initial_admin() is True
    service.activate(mailer.last_token(), PASSWORD)
    return service.list_accounts()[0]
