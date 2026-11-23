class DocumentError(Exception):
    """Base error safe to map to an HTTP problem response."""


class DocumentNotFound(DocumentError): pass
class DocumentDeleted(DocumentError): pass
class InvalidDocument(DocumentError): pass
class InvalidPageCursor(DocumentError): pass
class InvalidUpload(DocumentError): pass
class UploadTooLarge(InvalidUpload): pass
class UnsupportedMediaType(InvalidUpload): pass
class ConcurrentModification(DocumentError): pass
class ReferenceConflict(DocumentError): pass
class DependencyUnavailable(DocumentError): pass
class AccessPolicyUnavailable(DocumentError): pass
