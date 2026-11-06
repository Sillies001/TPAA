"""S3-compatible object-store adapter with TPAA-owned byte identity."""

from __future__ import annotations

import re
from importlib import import_module
from typing import Any

from .hashing import artifact_byte_hash
from .object_store import (
    ObjectStoreError,
    StoredObject,
    _logical_prefix_relative,
    _logical_relative,
)

_BUCKET = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")


def _error_code(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return ""
    error = response.get("Error")
    if not isinstance(error, dict):
        return ""
    code = error.get("Code")
    return "" if code is None else str(code)


class S3ObjectStore:
    """Physical S3-compatible store hidden behind TPAA logical URIs."""

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "tpaa",
        endpoint_url: str | None = None,
        region_name: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        if _BUCKET.fullmatch(bucket) is None:
            raise ValueError("S3 bucket name is invalid")
        normalized = prefix.strip("/")
        if not normalized or any(part in {"", ".", ".."} for part in normalized.split("/")):
            raise ValueError("S3 object prefix is invalid")
        if client is None:
            try:
                boto3 = import_module("boto3")
            except ModuleNotFoundError as exc:
                raise ObjectStoreError("S3 backend requires the service-s3 dependency") from exc
            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                region_name=region_name,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
            )
        self._bucket = bucket
        self._prefix = normalized
        self._client = client

    def _key(self, logical_uri: str) -> str:
        return f"{self._prefix}/{_logical_relative(logical_uri)}"

    def _logical_uri(self, key: str) -> str:
        root = f"{self._prefix}/"
        if not key.startswith(root):
            raise ObjectStoreError("S3 object escaped configured prefix")
        relative = key[len(root) :]
        parts = relative.split("/")
        if len(parts) < 3 or parts[0] not in {"tpaa-object", "tpaa-parquet"}:
            raise ObjectStoreError("S3 object layout is invalid")
        return f"{parts[0]}://{parts[1]}/{'/'.join(parts[2:])}"

    def ensure_ready(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception as exc:
            raise ObjectStoreError("S3 bucket is unavailable") from exc

    def _stored(self, logical_uri: str, data: bytes) -> StoredObject:
        return StoredObject(
            logical_uri=logical_uri,
            artifact_sha256=artifact_byte_hash(data),
            byte_size=len(data),
        )

    def put_bytes(self, logical_uri: str, data: bytes) -> StoredObject:
        stored = self._stored(logical_uri, data)
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=self._key(logical_uri),
                Body=data,
                Metadata={
                    "tpaa-sha256": stored.artifact_sha256,
                    "tpaa-logical-uri": logical_uri,
                },
            )
        except Exception as exc:
            raise ObjectStoreError("S3 object write failed") from exc
        return stored

    def put_bytes_immutable(self, logical_uri: str, data: bytes) -> StoredObject:
        stored = self._stored(logical_uri, data)
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=self._key(logical_uri),
                Body=data,
                IfNoneMatch="*",
                Metadata={
                    "tpaa-sha256": stored.artifact_sha256,
                    "tpaa-logical-uri": logical_uri,
                },
            )
            return stored
        except Exception as exc:
            if _error_code(exc) not in {"409", "412", "ConditionalRequestConflict", "PreconditionFailed"}:
                raise ObjectStoreError("S3 immutable object write failed") from exc
        try:
            existing = self.read_bytes(logical_uri)
        except ObjectStoreError as exc:
            raise ObjectStoreError("S3 immutable write conflict could not be verified") from exc
        if existing != data:
            raise ObjectStoreError(f"immutable object already exists: {logical_uri}")
        return stored

    def read_bytes(self, logical_uri: str) -> bytes:
        try:
            response = self._client.get_object(
                Bucket=self._bucket,
                Key=self._key(logical_uri),
            )
            value = response["Body"].read()
        except Exception as exc:
            raise ObjectStoreError(f"object missing: {logical_uri}") from exc
        if not isinstance(value, bytes):
            raise ObjectStoreError("S3 object body is not bytes")
        return value

    def verify(self, stored: StoredObject) -> bool:
        data = self.read_bytes(stored.logical_uri)
        return len(data) == stored.byte_size and artifact_byte_hash(data) == stored.artifact_sha256

    def list_objects(self, logical_prefix: str) -> tuple[StoredObject, ...]:
        prefix = f"{self._prefix}/{_logical_prefix_relative(logical_prefix)}"
        return self._inventory(prefix)

    def inventory(self) -> tuple[StoredObject, ...]:
        return self._inventory(f"{self._prefix}/")

    def _inventory(self, prefix: str) -> tuple[StoredObject, ...]:
        continuation: str | None = None
        keys: list[str] = []
        try:
            while True:
                parameters: dict[str, object] = {
                    "Bucket": self._bucket,
                    "Prefix": prefix,
                }
                if continuation is not None:
                    parameters["ContinuationToken"] = continuation
                response = self._client.list_objects_v2(**parameters)
                contents = response.get("Contents", [])
                if not isinstance(contents, list):
                    raise ObjectStoreError("S3 list response is invalid")
                for item in contents:
                    if not isinstance(item, dict) or not isinstance(item.get("Key"), str):
                        raise ObjectStoreError("S3 list item is invalid")
                    keys.append(str(item["Key"]))
                if response.get("IsTruncated") is not True:
                    break
                next_token = response.get("NextContinuationToken")
                if not isinstance(next_token, str) or not next_token:
                    raise ObjectStoreError("S3 continuation token is invalid")
                continuation = next_token
        except ObjectStoreError:
            raise
        except Exception as exc:
            raise ObjectStoreError("S3 object listing failed") from exc

        objects: list[StoredObject] = []
        for key in sorted(keys):
            logical_uri = self._logical_uri(key)
            objects.append(self._stored(logical_uri, self.read_bytes(logical_uri)))
        return tuple(objects)

    def delete_object(
        self,
        logical_uri: str,
        *,
        expected_sha256: str | None = None,
    ) -> bool:
        try:
            data = self.read_bytes(logical_uri)
        except ObjectStoreError:
            return False
        if expected_sha256 is not None and artifact_byte_hash(data) != expected_sha256:
            raise ObjectStoreError(f"object hash changed before delete: {logical_uri}")
        try:
            self._client.delete_object(Bucket=self._bucket, Key=self._key(logical_uri))
        except Exception as exc:
            raise ObjectStoreError("S3 object delete failed") from exc
        return True


__all__ = ["S3ObjectStore"]
