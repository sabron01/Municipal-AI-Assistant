from ..application.use_cases import DocumentService
from ..domain.ports import CategoryDirectory, DocumentAccessPolicy, ServiceDirectory
from ...accounts.service import DatabaseDocumentAccessPolicy
from .postgres_repositories import PostgresUnitOfWork, make_session_factory
from .rustfs_storage import RustFSObjectStorage
from .upload_validation import UploadValidator


def build_document_service(*, database_url: str, object_storage_endpoint: str,
    object_storage_access_key: str, object_storage_secret_key: str, object_storage_bucket: str,
    max_upload_bytes: int, allowed_media_types: frozenset[str], service_directory: ServiceDirectory,
    category_directory: CategoryDirectory, access_policy: DocumentAccessPolicy | None = None,
    verify_tls: bool = True) -> DocumentService:
    session_factory, _engine = make_session_factory(database_url)
    storage = RustFSObjectStorage(endpoint=object_storage_endpoint, access_key=object_storage_access_key,
        secret_key=object_storage_secret_key, bucket=object_storage_bucket, verify_tls=verify_tls)
    validator = UploadValidator(max_bytes=max_upload_bytes, allowed_media_types=allowed_media_types)
    effective_access_policy = access_policy or DatabaseDocumentAccessPolicy(session_factory)
    return DocumentService(lambda: PostgresUnitOfWork(session_factory), storage, validator,
        service_directory, category_directory, effective_access_policy)
