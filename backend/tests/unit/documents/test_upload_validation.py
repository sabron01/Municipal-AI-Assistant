from io import BytesIO
import pytest

from municipal_assistant.documents.domain.errors import UnsupportedMediaType, UploadTooLarge
from municipal_assistant.documents.infrastructure.upload_validation import UploadValidator


def test_upload_uses_detected_type_and_rewinds_staged_stream():
    pdf = b"%PDF-1.7\nexample document bytes"
    staged = UploadValidator(max_bytes=1024, allowed_media_types=frozenset({"application/pdf"})).stage(
        BytesIO(pdf), filename="../../report.pdf")
    try:
        assert staged.filename == "report.pdf"
        assert staged.mime_type == "application/pdf"
        assert staged.body.read() == pdf
    finally:
        staged.close()


def test_upload_is_rejected_when_format_is_not_configured():
    with pytest.raises(UnsupportedMediaType):
        UploadValidator(max_bytes=1024, allowed_media_types=frozenset()).stage(
            BytesIO(b"%PDF-1.7\nexample"), filename="report.pdf")


def test_encrypted_pdf_is_rejected():
    encrypted = (b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
                 b"trailer\n<< /Size 2 /Encrypt 2 0 R >>\nstartxref\n0\n%%EOF")

    with pytest.raises(UnsupportedMediaType, match="Encrypted PDF"):
        UploadValidator(max_bytes=1024, allowed_media_types=frozenset({"application/pdf"})).stage(
            BytesIO(encrypted), filename="protected.pdf")


def test_upload_size_limit_is_enforced_during_streaming():
    with pytest.raises(UploadTooLarge):
        UploadValidator(max_bytes=4, allowed_media_types=frozenset({"application/pdf"})).stage(
            BytesIO(b"%PDF-1.7"), filename="report.pdf")
