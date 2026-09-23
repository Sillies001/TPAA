"""M0 local object/Parquet abstraction with logical URI identity."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from tpaa_platform.filesync import InterProcessFileLock, atomic_replace_bytes
from tpaa_platform.filesystem import PlatformFilesystem, PlatformPathError

from .hashing import artifact_byte_hash


class ObjectStoreError(ValueError):
    """Logical object URI or local object operation is invalid."""


@dataclass(frozen=True)
class StoredObject:
    logical_uri: str
    artifact_sha256: str
    byte_size: int


def _logical_relative(logical_uri: str) -> str:
    parsed = urlsplit(logical_uri)
    if parsed.scheme not in {"tpaa-object", "tpaa-parquet"}:
        raise ObjectStoreError("unsupported logical object scheme")
    if not parsed.netloc:
        raise ObjectStoreError("logical object URI requires a namespace")
    if parsed.query or parsed.fragment or parsed.username or parsed.password or parsed.port:
        raise ObjectStoreError("logical object URI may not contain credentials/query/fragment/port")
    path = parsed.path.lstrip("/")
    if not path:
        raise ObjectStoreError("logical object URI requires a path")
    return f"{parsed.scheme}/{parsed.netloc}/{path}"


class LocalObjectStore:
    """Physical local store hidden behind stable logical URI references."""

    def __init__(self, root: Path) -> None:
        self.filesystem = PlatformFilesystem(root)

    def physical_path(self, logical_uri: str) -> Path:
        try:
            return self.filesystem.resolve(_logical_relative(logical_uri))
        except PlatformPathError as exc:
            raise ObjectStoreError(str(exc)) from exc

    def put_bytes(self, logical_uri: str, data: bytes) -> StoredObject:
        target = self.physical_path(logical_uri)
        lock = InterProcessFileLock(target.with_name(f".{target.name}.lock"))
        with lock:
            atomic_replace_bytes(target, data)
        return StoredObject(
            logical_uri=logical_uri,
            artifact_sha256=artifact_byte_hash(data),
            byte_size=len(data),
        )

    def read_bytes(self, logical_uri: str) -> bytes:
        path = self.physical_path(logical_uri)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise ObjectStoreError(f"object missing: {logical_uri}") from exc

    def verify(self, stored: StoredObject) -> bool:
        data = self.read_bytes(stored.logical_uri)
        return len(data) == stored.byte_size and artifact_byte_hash(data) == stored.artifact_sha256
