"""M1 staging-to-sealed immutable object flow built on the M0 logical object store."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from .object_store import LocalObjectStore, ObjectStoreError, StoredObject


class ObjectSealError(RuntimeError):
    """Fail-closed staging/sealing error."""


@dataclass(frozen=True)
class StagedObject:
    operation_id: str
    staging: StoredObject
    sealed_uri: str


def _staging_uri(sealed_uri: str, operation_id: str, sha256: str) -> str:
    if not operation_id or "/" in operation_id or "\\" in operation_id:
        raise ObjectSealError("invalid operation_id")
    parsed = urlsplit(sealed_uri)
    if parsed.scheme not in {"tpaa-object", "tpaa-parquet"} or not parsed.netloc:
        raise ObjectSealError("invalid sealed logical URI")
    suffix = PurePosixPath(parsed.path).name or "object"
    return f"{parsed.scheme}://staging/{operation_id}/{sha256}-{suffix}"


class LocalSealedObjectFlow:
    """Explicit stage/verify/seal/cleanup flow without hidden database semantics."""

    def __init__(self, store: LocalObjectStore) -> None:
        self._store = store

    def stage(self, *, sealed_uri: str, data: bytes, operation_id: str) -> StagedObject:
        sha256 = hashlib.sha256(data).hexdigest()
        staging_uri = _staging_uri(sealed_uri, operation_id, sha256)
        stored = self._store.put_bytes(staging_uri, data)
        if stored.artifact_sha256 != sha256 or not self._store.verify(stored):
            raise ObjectSealError("staging verification failed")
        return StagedObject(operation_id=operation_id, staging=stored, sealed_uri=sealed_uri)

    def seal(self, staged: StagedObject) -> StoredObject:
        if not self._store.verify(staged.staging):
            raise ObjectSealError("staged object verification failed")
        data = self._store.read_bytes(staged.staging.logical_uri)
        target = self._store.physical_path(staged.sealed_uri)
        if target.exists():
            try:
                existing = self._store.read_bytes(staged.sealed_uri)
            except ObjectStoreError as exc:
                raise ObjectSealError(str(exc)) from exc
            if hashlib.sha256(existing).hexdigest() != staged.staging.artifact_sha256:
                raise ObjectSealError("sealed logical URI already contains different bytes")
            result = StoredObject(
                logical_uri=staged.sealed_uri,
                artifact_sha256=staged.staging.artifact_sha256,
                byte_size=len(existing),
            )
        else:
            result = self._store.put_bytes(staged.sealed_uri, data)
        if not self._store.verify(result):
            raise ObjectSealError("sealed object verification failed")
        self.cleanup(staged)
        return result

    def cleanup(self, staged: StagedObject) -> bool:
        """Remove a known orphan/cancelled staging object; sealed bytes are untouched."""

        path = self._store.physical_path(staged.staging.logical_uri)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
