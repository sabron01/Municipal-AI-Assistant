from hashlib import sha256 as digest
from pathlib import PurePath
from tempfile import SpooledTemporaryFile
from zipfile import BadZipFile, ZipFile

from ..domain.errors import InvalidUpload, UnsupportedMediaType, UploadTooLarge
from ..domain.ports import StagedUpload
from ..domain.value_objects import OriginalFilename, Sha256


def detect_media_type(body, *, max_uncompressed_bytes: int) -> str:
    head = body.read(16)
    body.seek(0)
    if head.startswith(b"%PDF-"): return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"): return "image/png"
    if head.startswith(b"\xff\xd8\xff"): return "image/jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")): return "image/gif"
    if head.startswith((b"II*\x00", b"MM\x00*")): return "image/tiff"
    try:
        if head.startswith(b"PK\x03\x04"):
            with ZipFile(body) as archive:
                entries = archive.infolist()
                expanded_size = sum(entry.file_size for entry in entries)
                compressed_size = max(1, sum(entry.compress_size for entry in entries))
                if (len(entries) > 1000 or expanded_size > max_uncompressed_bytes
                        or expanded_size / compressed_size > 100):
                    raise InvalidUpload("Archive exceeds safe inspection limits")
                names = set(archive.namelist())
                if "[Content_Types].xml" not in names:
                    return "application/zip"
                with archive.open("[Content_Types].xml") as metadata:
                    content_types = metadata.read(2 * 1024 * 1024 + 1)
                if len(content_types) > 2 * 1024 * 1024:
                    raise InvalidUpload("Office document metadata exceeds inspection limit")
                if b"wordprocessingml.document" in content_types and "word/document.xml" in names:
                    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if b"spreadsheetml.sheet" in content_types and "xl/workbook.xml" in names:
                    return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                if b"presentationml.presentation" in content_types and "ppt/presentation.xml" in names:
                    return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                return "application/zip"
            raise UnsupportedMediaType("File signature is not supported")
        raise UnsupportedMediaType("File signature is not supported")
    except BadZipFile as exc:
        raise InvalidUpload("Malformed archive") from exc
    finally:
        body.seek(0)


class StagedFile:
    def __init__(self, body, filename, mime_type, size_bytes, sha256):
        self.body, self.filename, self.mime_type = body, filename, mime_type
        self.size_bytes, self.sha256 = size_bytes, Sha256(sha256)
    def close(self): self.body.close()


class UploadValidator:
    def __init__(self, *, max_bytes: int, allowed_media_types: frozenset[str]):
        if max_bytes < 1:
            raise ValueError("DOCUMENT_MAX_UPLOAD_BYTES must be positive")
        self.max_bytes, self.allowed_media_types = max_bytes, allowed_media_types

    def stage(self, body, *, filename: str) -> StagedFile:
        safe_name = OriginalFilename(filename).value
        staged = SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b")
        checksum, size = digest(), 0
        try:
            while chunk := body.read(1024 * 1024):
                size += len(chunk)
                if size > self.max_bytes:
                    raise UploadTooLarge("Upload exceeds configured size limit")
                checksum.update(chunk)
                staged.write(chunk)
            if size == 0:
                raise InvalidUpload("Empty files are not accepted")
            staged.seek(0)
            media_type = detect_media_type(staged, max_uncompressed_bytes=self.max_bytes)
            if media_type not in self.allowed_media_types:
                raise UnsupportedMediaType("Detected file type is not enabled")
            # Extension is display-only; detected signature is authoritative.
            return StagedFile(staged, safe_name, media_type, size, checksum.hexdigest())
        except Exception:
            staged.close()
            raise
