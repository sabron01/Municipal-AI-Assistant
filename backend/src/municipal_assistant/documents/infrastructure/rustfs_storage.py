import base64
from dataclasses import dataclass
from botocore.exceptions import BotoCoreError, ClientError
import boto3
from botocore.config import Config

from ..domain.errors import DependencyUnavailable, DocumentNotFound
from ..domain.ports import StoredObjectMetadata, StoredObjectReceipt
from ..domain.value_objects import ObjectKey, Sha256


@dataclass
class S3ReadableObject:
    response: dict
    filename: str
    @property
    def body(self): return self.response["Body"]
    @property
    def content_length(self): return self.response["ContentLength"]
    @property
    def content_type(self): return self.response.get("ContentType", "application/octet-stream")
    def close(self): self.body.close()


class RustFSObjectStorage:
    """S3-compatible adapter; endpoint and bucket are explicit configuration."""
    def __init__(self, *, endpoint: str, access_key: str, secret_key: str, bucket: str,
                 region: str = "us-east-1", verify_tls: bool = True):
        self.bucket = bucket
        self.client = boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=access_key,
            aws_secret_access_key=secret_key, region_name=region, verify=verify_tls,
            config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3, "mode": "standard"}))

    def put(self, *, key: ObjectKey, body, content_length: int, content_type: str,
            checksum_sha256: Sha256) -> StoredObjectReceipt:
        try:
            self.client.put_object(Bucket=self.bucket, Key=key.value, Body=body, ContentLength=content_length,
                ContentType=content_type, Metadata={"sha256": checksum_sha256.value},
                ChecksumAlgorithm="SHA256",
                ChecksumSHA256=base64.b64encode(bytes.fromhex(checksum_sha256.value)).decode())
            return StoredObjectReceipt(key, content_length, checksum_sha256)
        except (BotoCoreError, ClientError) as exc:
            raise DependencyUnavailable("Object storage write failed") from exc

    def head(self, key: ObjectKey) -> StoredObjectMetadata | None:
        try:
            item = self.client.head_object(Bucket=self.bucket, Key=key.value, ChecksumMode="ENABLED")
            checksum = item.get("ChecksumSHA256")
            if not checksum:
                raise DependencyUnavailable("RustFS did not return a server-verified object checksum")
            digest = base64.b64decode(checksum, validate=True).hex()
            return StoredObjectMetadata(key, item["ContentLength"], Sha256(digest),
                                        item.get("ContentType", "application/octet-stream"))
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return None
            raise DependencyUnavailable("Object storage metadata request failed") from exc
        except BotoCoreError as exc:
            raise DependencyUnavailable("Object storage metadata request failed") from exc

    def open(self, key: ObjectKey, *, filename: str) -> S3ReadableObject:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key.value)
            return S3ReadableObject(response, filename)
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                raise DocumentNotFound("Stored document was not found") from exc
            raise DependencyUnavailable("Object storage read failed") from exc
        except BotoCoreError as exc:
            raise DependencyUnavailable("Object storage read failed") from exc

    def delete(self, key: ObjectKey) -> None:
        # Available to a future approved retention worker only; no HTTP route calls this.
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key.value)
        except (BotoCoreError, ClientError) as exc:
            raise DependencyUnavailable("Object storage delete failed") from exc
