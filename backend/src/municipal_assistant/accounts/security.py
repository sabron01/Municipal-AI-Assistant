import hashlib
import secrets
from hmac import compare_digest

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from email_validator import EmailNotValidError, validate_email

_password_hasher = PasswordHasher(type=Type.ID, memory_cost=19_456, time_cost=2, parallelism=1)


def normalize_email(value: str) -> str:
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized.casefold()
    except EmailNotValidError as exc:
        raise ValueError("A valid professional email address is required") from exc


def validate_password(value: str) -> None:
    if len(value) < 15 or len(value) > 128:
        raise ValueError("Password must contain between 15 and 128 characters")


def hash_password(value: str) -> str:
    validate_password(value)
    return _password_hasher.hash(value)


def verify_password(encoded: str | None, value: str) -> bool:
    if not encoded:
        return False
    try:
        return _password_hasher.verify(encoded, value)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def issue_secret() -> str:
    return secrets.token_urlsafe(32)


def digest_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def secure_equal(left: str, right: str) -> bool:
    return compare_digest(left, right)
