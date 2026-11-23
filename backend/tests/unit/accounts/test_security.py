import pytest

from municipal_assistant.accounts.security import (
    digest_secret,
    hash_password,
    issue_secret,
    normalize_email,
    secure_equal,
    validate_password,
    verify_password,
)

PASSWORD = "correct horse battery staple"


def test_normalize_email_trims_and_casefolds():
    assert normalize_email("  Agent.Municipal@Tataouine.TN  ") == "agent.municipal@tataouine.tn"


@pytest.mark.parametrize("value", ["", "not-an-email", "agent@", "@tataouine.tn"])
def test_normalize_email_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        normalize_email(value)


def test_password_length_boundaries_are_enforced():
    with pytest.raises(ValueError):
        validate_password("a" * 14)
    validate_password("a" * 15)
    validate_password("a" * 128)
    with pytest.raises(ValueError):
        validate_password("a" * 129)


def test_hash_password_produces_argon2id_and_verifies():
    encoded = hash_password(PASSWORD)

    assert encoded.startswith("$argon2id$")
    assert verify_password(encoded, PASSWORD) is True
    assert verify_password(encoded, PASSWORD + "x") is False


def test_verify_password_rejects_missing_or_malformed_hash():
    assert verify_password(None, PASSWORD) is False
    assert verify_password("", PASSWORD) is False
    assert verify_password("not-a-valid-hash", PASSWORD) is False


def test_issue_secret_is_unique_and_url_safe():
    first, second = issue_secret(), issue_secret()

    assert first != second
    assert len(first) >= 40
    assert "=" not in first


def test_digest_secret_is_deterministic_sha256_hex():
    digest = digest_secret("session-token")

    assert digest == digest_secret("session-token")
    assert len(digest) == 64
    assert set(digest) <= set("0123456789abcdef")


def test_secure_equal_compares_without_raising_on_different_lengths():
    assert secure_equal("csrf-token", "csrf-token") is True
    assert secure_equal("csrf-token", "csrf-tokeN") is False
    assert secure_equal("short", "a much longer value") is False
