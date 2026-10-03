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


def _parse_logical_uri(logical_uri: str) -> tuple[str, str, str]:
    parsed = urlsplit(logical_uri)
    if parsed.scheme not in {"tpaa-object", "tpaa-parquet"}:
        raise ObjectStoreError("unsupported logical object scheme")
    if not parsed.netloc:
        raise ObjectStoreError("logical object URI requires a namespace")
    if parsed.query or parsed.fragment or parsed.username or parsed.password or parsed.port:
        raise ObjectStoreError(
            "logical object URI may not contain credentials/query/fragment/port"
        )
    return parsed.scheme, parsed.netloc, parsed.path.lstrip("/")


def _logical_relative(logical_uri: str) -> str:
    scheme, namespace, path = _parse_logical_uri(logical_uri)
    if not path:
        raise ObjectStoreError("logical object URI requires a path")
    return f"{scheme}/{namespace}/{path}"


def _logical_prefix_relative(logical_prefix: str) -> str:
    scheme, namespace, path = _parse_logical_uri(logical_prefix)
    if not path:
        return f"{scheme}/{namespace}"
    return f"{scheme}/{namespace}/{path}"


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
        return (
            len(data) == stored.byte_size
            and artifact_byte_hash(data) == stored.artifact_sha256
        )

    def list_objects(self, logical_prefix: str) -> tuple[StoredObject, ...]:
        """Enumerate durable objects below one governed logical prefix."""

        relative = _logical_prefix_relative(logical_prefix)
        base = self.filesystem.resolve(relative)
        if not base.exists():
            return ()
        candidates = [base] if base.is_file() else sorted(base.rglob("*"))
        objects: list[StoredObject] = []
        for path in candidates:
            if not path.is_file():
                continue
            if path.name.startswith(".") or path.name.endswith(".lock"):
                continue
            relative_path = path.resolve().relative_to(self.filesystem.root)
            parts = relative_path.parts
            if len(parts) < 3 or parts[0] not in {"tpaa-object", "tpaa-parquet"}:
                raise ObjectStoreError("physical object layout is invalid")
            logical_uri = f"{parts[0]}://{parts[1]}/{'/'.join(parts[2:])}"
            data = path.read_bytes()
            objects.append(
                StoredObject(
                    logical_uri=logical_uri,
                    artifact_sha256=artifact_byte_hash(data),
                    byte_size=len(data),
                )
            )
        return tuple(objects)

    def delete_object(
        self,
        logical_uri: str,
        *,
        expected_sha256: str | None = None,
    ) -> bool:
        """Delete one known orphan only when optional byte identity still matches."""

        target = self.physical_path(logical_uri)
        lock = InterProcessFileLock(target.with_name(f".{target.name}.lock"))
        with lock:
            if not target.exists():
                return False
            if expected_sha256 is not None:
                actual = artifact_byte_hash(target.read_bytes())
                if actual != expected_sha256:
                    raise ObjectStoreError(
                        "object hash changed before delete: "
                        f"{logical_uri}"
                    )
            target.unlink()
            return True
