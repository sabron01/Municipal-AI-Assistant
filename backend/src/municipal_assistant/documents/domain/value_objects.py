from dataclasses import dataclass
from uuid import UUID
import re


@dataclass(frozen=True, slots=True)
class DocumentId:
    value: UUID

@dataclass(frozen=True, slots=True)
class VersionId:
    value: UUID

@dataclass(frozen=True, slots=True)
class ServiceId:
    value: UUID

@dataclass(frozen=True, slots=True)
class CategoryId:
    value: UUID

@dataclass(frozen=True, slots=True)
class ActorId:
    value: UUID

@dataclass(frozen=True, slots=True)
class Sha256:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.lower()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized):
            raise ValueError("SHA-256 must contain exactly 64 hexadecimal characters")
        object.__setattr__(self, "value", normalized)

@dataclass(frozen=True, slots=True)
class ObjectKey:
    value: str

    def __post_init__(self) -> None:
        if not self.value or self.value.startswith("/") or ".." in self.value.split("/"):
            raise ValueError("Object key must be a non-empty relative key")

@dataclass(frozen=True, slots=True)
class OriginalFilename:
    value: str

    def __post_init__(self) -> None:
        cleaned = self.value.replace("\\", "/").split("/")[-1].replace("\r", "").replace("\n", "").strip()
        if not cleaned or len(cleaned) > 255 or cleaned in {".", ".."}:
            raise ValueError("Invalid original filename")
        object.__setattr__(self, "value", cleaned)

@dataclass(frozen=True, slots=True)
class MimeType:
    value: str

    def __post_init__(self) -> None:
        if "/" not in self.value or any(c in self.value for c in "\r\n"):
            raise ValueError("Invalid media type")

@dataclass(frozen=True, slots=True)
class ByteSize:
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError("Byte size must be positive")
