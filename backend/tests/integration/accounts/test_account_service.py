from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from municipal_assistant.accounts.models import (
    AccountAuditRow,
    AccountLoginAttemptRow,
    AccountRow,
    AccountSessionRow,
    AccountTokenRow,
)
from municipal_assistant.accounts.security import digest_secret, normalize_email
from municipal_assistant.accounts.service import (
    AccountConflict,
    AccountNotFound,
    DatabaseDocumentAccessPolicy,
    InvalidAccountToken,
)
from municipal_assistant.documents.domain.errors import AccessPolicyUnavailable, DocumentNotFound
from municipal_assistant.documents.domain.value_objects import ServiceId

PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "another correct horse battery"
IP = "203.0.113.10"


def create_active_account(service, mailer, email="agent@municipal.tn", *, password=PASSWORD):
    account = service.create_account(uuid4(), email)
    service.activate(mailer.last_token(), password)
    return service.get_account(account.id)


def bootstrap_active_admin(service, mailer, email="admin@municipal.tn"):
    assert service.bootstrap_initial_admin() is True
    service.activate(mailer.last_token(), PASSWORD)
    return service.list_accounts()[0]


def test_bootstrap_creates_a_pending_central_admin_and_sends_an_activation_link(build_service, mailer):
    service = build_service(initial_admin_email="Admin@Municipal.TN")

    assert service.bootstrap_initial_admin() is True

    [account] = service.list_accounts()
    assert account.status == "pending"
    assert account.is_central_admin is True
    assert account.normalized_email == "admin@municipal.tn"
    assert mailer.messages[-1].recipient == "Admin@Municipal.TN"
    assert "activate" in mailer.messages[-1].body


def test_bootstrap_is_idempotent_once_the_admin_is_active(build_service, mailer):
    service = build_service(initial_admin_email="admin@municipal.tn")
    admin = bootstrap_active_admin(service, mailer)
    sent = len(mailer.messages)

    assert service.bootstrap_initial_admin() is False
    assert len(mailer.messages) == sent
    assert service.get_account(admin.id).status == "active"


def test_bootstrap_rejects_an_email_owned_by_a_non_admin(build_service, mailer):
    service = build_service(initial_admin_email="agent@municipal.tn")
    service.create_account(uuid4(), "agent@municipal.tn")

    with pytest.raises(AccountConflict):
        service.bootstrap_initial_admin()


def test_activation_sets_the_password_activates_the_account_and_is_single_use(build_service, mailer):
    service = build_service()
    account = service.create_account(uuid4(), "agent@municipal.tn")
    token = mailer.last_token()

    service.activate(token, PASSWORD)

    activated = service.get_account(account.id)
    assert activated.status == "active"
    assert activated.password_hash
    with pytest.raises(InvalidAccountToken):
        service.activate(token, PASSWORD)


def test_expired_activation_token_is_rejected(build_service, mailer, session_factory):
    service = build_service()
    account = service.create_account(uuid4(), "agent@municipal.tn")
    token = mailer.last_token()
    with session_factory() as session:
        record = session.scalar(select(AccountTokenRow).where(
            AccountTokenRow.account_id == account.id, AccountTokenRow.purpose == "activation"))
        record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()

    with pytest.raises(InvalidAccountToken):
        service.activate(token, PASSWORD)


def test_create_account_rejects_duplicates_case_insensitively_and_invalid_emails(build_service, mailer):
    service = build_service()
    service.create_account(uuid4(), "agent@municipal.tn")

    with pytest.raises(AccountConflict):
        service.create_account(uuid4(), "AGENT@Municipal.TN")
    with pytest.raises(ValueError):
        service.create_account(uuid4(), "not-an-email")


def test_login_returns_a_session_that_resolves_to_the_account(build_service, mailer):
    service = build_service()
    account = create_active_account(service, mailer)

    result = service.authenticate("AGENT@municipal.tn", PASSWORD, IP)

    assert result is not None
    authenticated, session_token, csrf_token = result
    assert authenticated.id == account.id
    pair = service.current_session(session_token)
    assert pair is not None
    assert pair[0].id == account.id
    assert pair[1].csrf_hash == digest_secret(csrf_token)


def test_login_rejects_wrong_password_unknown_email_pending_and_disabled_accounts(build_service, mailer):
    service = build_service()
    account = create_active_account(service, mailer)
    pending = service.create_account(uuid4(), "pending@municipal.tn")

    assert service.authenticate(account.email, "wrong password value", IP) is None
    assert service.authenticate("unknown@municipal.tn", PASSWORD, IP) is None
    assert service.authenticate(pending.email, PASSWORD, IP) is None

    service.set_account_status(uuid4(), account.id, "disabled")
    assert service.authenticate(account.email, PASSWORD, IP) is None


def test_login_is_throttled_after_ten_failures_for_the_same_email(build_service, mailer):
    service = build_service()
    account = create_active_account(service, mailer)

    for _ in range(10):
        assert service.authenticate(account.email, "wrong password value", IP) is None

    assert service.authenticate(account.email, PASSWORD, IP) is None


def test_login_is_throttled_after_one_hundred_failures_from_the_same_ip(
        build_service, mailer, session_factory):
    service = build_service()
    account = create_active_account(service, mailer)
    now = datetime.now(timezone.utc)
    with session_factory() as session:
        for _ in range(100):
            session.add(AccountLoginAttemptRow(
                email_hash=digest_secret(normalize_email("other@municipal.tn")),
                ip_hash=digest_secret(IP),
                successful=False,
                attempted_at=now,
            ))
        session.commit()

    assert service.authenticate(account.email, PASSWORD, IP) is None


def test_expired_session_is_rejected_and_logout_revokes_the_session(
        build_service, mailer, session_factory):
    service = build_service()
    create_active_account(service, mailer)
    _, first_token, _ = service.authenticate("agent@municipal.tn", PASSWORD, IP)
    with session_factory() as session:
        record = session.scalar(select(AccountSessionRow).where(
            AccountSessionRow.token_hash == digest_secret(first_token)))
        record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()
    assert service.current_session(first_token) is None

    _, second_token, _ = service.authenticate("agent@municipal.tn", PASSWORD, IP)
    service.logout(second_token)
    assert service.current_session(second_token) is None
    service.logout(second_token)


def test_disabling_an_account_revokes_its_active_sessions(build_service, mailer):
    service = build_service()
    account = create_active_account(service, mailer)
    _, session_token, _ = service.authenticate(account.email, PASSWORD, IP)

    service.set_account_status(uuid4(), account.id, "disabled")

    assert service.current_session(session_token) is None


def test_password_reset_rotates_the_password_and_revokes_existing_sessions(build_service, mailer):
    service = build_service()
    account = create_active_account(service, mailer)
    _, session_token, _ = service.authenticate(account.email, PASSWORD, IP)

    service.request_password_reset(uuid4(), account.id)
    token = mailer.last_token()
    service.reset_password(token, NEW_PASSWORD)

    assert service.current_session(session_token) is None
    assert service.authenticate(account.email, PASSWORD, IP) is None
    assert service.authenticate(account.email, NEW_PASSWORD, IP) is not None
    with pytest.raises(InvalidAccountToken):
        service.reset_password(token, PASSWORD)


def test_password_reset_requires_an_active_account(build_service, mailer):
    service = build_service()
    pending = service.create_account(uuid4(), "pending@municipal.tn")

    with pytest.raises(AccountNotFound):
        service.request_password_reset(uuid4(), pending.id)
    with pytest.raises(AccountNotFound):
        service.request_password_reset(uuid4(), uuid4())


def test_last_active_central_admin_cannot_be_disabled_or_demoted(build_service, mailer):
    service = build_service(initial_admin_email="admin@municipal.tn")
    admin = bootstrap_active_admin(service, mailer)

    with pytest.raises(AccountConflict):
        service.set_account_status(admin.id, admin.id, "disabled")
    with pytest.raises(AccountConflict):
        service.set_central_admin(admin.id, admin.id, False)

    other = create_active_account(service, mailer, "second@municipal.tn")
    service.set_central_admin(admin.id, other.id, True)
    service.set_account_status(admin.id, admin.id, "disabled")

    assert service.get_account(admin.id).status == "disabled"


def test_account_status_transitions_are_restricted(build_service, mailer, session_factory):
    service = build_service()
    account = create_active_account(service, mailer)

    with pytest.raises(AccountConflict):
        service.set_account_status(uuid4(), account.id, "active")
    with pytest.raises(ValueError):
        service.set_account_status(uuid4(), account.id, "pending")

    service.set_account_status(uuid4(), account.id, "disabled")
    assert service.get_account(account.id).status == "disabled"
    service.set_account_status(uuid4(), account.id, "active")
    assert service.get_account(account.id).status == "active"

    pending = service.create_account(uuid4(), "pending@municipal.tn")
    with pytest.raises(AccountConflict):
        service.set_account_status(uuid4(), pending.id, "active")
    with session_factory() as session:
        row = session.get(AccountRow, pending.id)
        row.status = "disabled"
        session.commit()
    with pytest.raises(AccountConflict):
        service.set_account_status(uuid4(), pending.id, "active")


def test_replace_permissions_scopes_access_and_clears_previous_grants(
        build_service, mailer, session_factory):
    service = build_service(initial_admin_email="admin@municipal.tn")
    admin = bootstrap_active_admin(service, mailer)
    user = create_active_account(service, mailer, "user@municipal.tn")
    service_id = uuid4()
    policy = DatabaseDocumentAccessPolicy(session_factory)

    service.replace_permissions(admin.id, user.id, service_id,
                                {"document.read", "document.create"})

    policy.require(user.id, "document.read", ServiceId(service_id))
    policy.require(user.id, "document.list", ServiceId(service_id))
    with pytest.raises(DocumentNotFound):
        policy.require(user.id, "document.soft_delete", ServiceId(service_id))
    assert policy.permissions_for(user.id, service_id) == ["document.create", "document.read"]
    assert policy.permissions_by_service(user.id) == {
        str(service_id): ["document.create", "document.read"]}

    service.replace_permissions(admin.id, user.id, service_id, {"document.soft_delete"})

    with pytest.raises(DocumentNotFound):
        policy.require(user.id, "document.read", ServiceId(service_id))
    assert policy.permissions_for(user.id, service_id) == ["document.soft_delete"]


def test_permission_replacement_rejects_unknown_permissions_and_accounts(build_service, mailer):
    service = build_service()
    user = create_active_account(service, mailer)

    with pytest.raises(ValueError):
        service.replace_permissions(uuid4(), user.id, uuid4(), {"document.publish"})
    with pytest.raises(AccountNotFound):
        service.replace_permissions(uuid4(), uuid4(), uuid4(), {"document.read"})


def test_access_policy_rejects_unknown_actions_and_inactive_accounts(
        build_service, mailer, session_factory):
    service = build_service(initial_admin_email="admin@municipal.tn")
    admin = bootstrap_active_admin(service, mailer)
    user = create_active_account(service, mailer, "user@municipal.tn")
    service_id = uuid4()
    policy = DatabaseDocumentAccessPolicy(session_factory)
    service.replace_permissions(admin.id, user.id, service_id, {"document.read"})

    with pytest.raises(AccessPolicyUnavailable):
        policy.require(user.id, "document.publish", ServiceId(service_id))
    assert policy.is_central_admin(admin.id) is True
    assert policy.is_central_admin(user.id) is False

    service.set_account_status(uuid4(), user.id, "disabled")
    with pytest.raises(DocumentNotFound):
        policy.require(user.id, "document.read", ServiceId(service_id))


def test_failed_login_is_audited(build_service, mailer, session_factory):
    service = build_service()
    account = create_active_account(service, mailer)

    service.authenticate(account.email, "wrong password value", IP)

    with session_factory() as session:
        actions = list(session.scalars(select(AccountAuditRow.action)))
    assert "auth.login_denied" in actions
