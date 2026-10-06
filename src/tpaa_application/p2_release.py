"""PRCB C2 P2 release/CAS persistence over existing DB 1.9 authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid5

from tpaa_storage.canonical_rows import CanonicalRowRepository

_P2_RELEASE_NAMESPACE = UUID("637dd099-1e59-4d40-8702-ce0ba746f907")


class P2ReleaseError(RuntimeError):
    """Fail-closed P2 analysis-release publication error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class P2ReleaseLineage:
    session_id: str
    catalog_version: str
    catalog_hash: str
    context_binding_hash: str


@dataclass(frozen=True, slots=True)
class P2PublishedRelease:
    release_id: str
    scope_key: str
    session_id: str
    version_token: int
    parent_release_id: str | None
    manifest_hash: str
    reused: bool


def _uuid(value: str, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise P2ReleaseError("P2_RELEASE_UUID_INVALID", field) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise P2ReleaseError("P2_RELEASE_UUID_INVALID", field)
    return value


def _hash64(value: str, field: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise P2ReleaseError("P2_RELEASE_HASH_INVALID", field)
    return value


def _required_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise P2ReleaseError("P2_RELEASE_INTEGER_INVALID", field)
    return value


def _utc(value: str, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P2ReleaseError("P2_RELEASE_TIME_INVALID", field) from exc
    if parsed.tzinfo is None:
        raise P2ReleaseError("P2_RELEASE_TIME_INVALID", field)
    return value


def p2_release_scope_key(source_observation_id: str) -> str:
    return f"P2:{_uuid(source_observation_id, 'source_observation_id')}"


def allocate_p2_release_id(
    *,
    job_id: str,
    request_hash: str,
    scope_key: str,
) -> str:
    _uuid(job_id, "job_id")
    _hash64(request_hash, "request_hash")
    if not scope_key.strip():
        raise P2ReleaseError("P2_RELEASE_SCOPE_KEY_INVALID", scope_key)
    return str(uuid5(_P2_RELEASE_NAMESPACE, f"{job_id}|{request_hash}|{scope_key}"))


class P2ReleaseRepository:
    """Publish a P2 analysis_release through the already-running formal Job."""

    def __init__(self, rows: CanonicalRowRepository) -> None:
        self._rows = rows

    def source_lineage(self, source_release_id: str) -> P2ReleaseLineage:
        _uuid(source_release_id, "source_release_id")
        row = self._rows.one(
            "registry.analysis_release",
            where={"release_id": source_release_id},
            columns=(
                "session_id",
                "catalog_version",
                "catalog_hash",
                "context_binding_hash",
                "status",
                "manifest_hash",
                "published_at",
            ),
        )
        if (
            row is None
            or row["session_id"] is None
            or row["published_at"] is None
            or str(row["status"]) != "PUBLISHED"
        ):
            raise P2ReleaseError(
                "P2_SOURCE_RELEASE_NOT_PUBLISHED",
                source_release_id,
            )
        _hash64(str(row["manifest_hash"]), "source_manifest_hash")
        return P2ReleaseLineage(
            session_id=_uuid(str(row["session_id"]), "session_id"),
            catalog_version=str(row["catalog_version"]),
            catalog_hash=_hash64(str(row["catalog_hash"]), "catalog_hash"),
            context_binding_hash=_hash64(
                str(row["context_binding_hash"]),
                "context_binding_hash",
            ),
        )

    def publish(
        self,
        *,
        job_id: str,
        release_id: str,
        scope_key: str,
        lineage: P2ReleaseLineage,
        expected_version_token: int,
        manifest_hash: str,
        published_at_utc: str,
    ) -> P2PublishedRelease:
        _uuid(job_id, "job_id")
        _uuid(release_id, "release_id")
        _uuid(lineage.session_id, "session_id")
        _hash64(lineage.catalog_hash, "catalog_hash")
        _hash64(lineage.context_binding_hash, "context_binding_hash")
        _hash64(manifest_hash, "manifest_hash")
        _utc(published_at_utc, "published_at_utc")
        if not scope_key.strip():
            raise P2ReleaseError("P2_RELEASE_SCOPE_KEY_INVALID", scope_key)
        if expected_version_token < 0:
            raise P2ReleaseError(
                "P2_RELEASE_EXPECTED_VERSION_INVALID",
                str(expected_version_token),
            )

        job = self._rows.one(
            "registry.compute_job",
            where={"job_id": job_id},
            columns=("status", "session_id"),
        )
        if job is None or str(job["status"]) != "RUNNING":
            raise P2ReleaseError("P2_RELEASE_JOB_NOT_RUNNING", job_id)
        if job["session_id"] is None:
            self._rows.update_exact(
                "registry.compute_job",
                where={"job_id": job_id, "status": "RUNNING"},
                values={"session_id": lineage.session_id},
            )
        elif str(job["session_id"]) != lineage.session_id:
            raise P2ReleaseError(
                "P2_RELEASE_JOB_SESSION_MISMATCH",
                job_id,
            )

        existing = self._rows.one(
            "registry.analysis_release",
            where={"release_id": release_id},
            columns=(
                "scope_type",
                "scope_key",
                "session_id",
                "release_no",
                "compute_job_id",
                "catalog_version",
                "catalog_hash",
                "context_binding_hash",
                "status",
                "parent_release_id",
                "manifest_hash",
            ),
        )
        if existing is not None:
            if (
                str(existing["scope_type"]) != "SESSION"
                or str(existing["scope_key"]) != scope_key
                or str(existing["session_id"]) != lineage.session_id
                or str(existing["compute_job_id"]) != job_id
                or str(existing["catalog_version"]) != lineage.catalog_version
                or str(existing["catalog_hash"]) != lineage.catalog_hash
                or str(existing["context_binding_hash"])
                != lineage.context_binding_hash
                or str(existing["status"]) != "PUBLISHED"
                or str(existing["manifest_hash"]) != manifest_hash
            ):
                raise P2ReleaseError(
                    "P2_RELEASE_IMMUTABLE_CONFLICT",
                    release_id,
                )
            return P2PublishedRelease(
                release_id=release_id,
                scope_key=scope_key,
                session_id=lineage.session_id,
                version_token=_required_int(
                    existing["release_no"],
                    "analysis_release.release_no",
                ),
                parent_release_id=(
                    None
                    if existing["parent_release_id"] is None
                    else str(existing["parent_release_id"])
                ),
                manifest_hash=manifest_hash,
                reused=True,
            )

        pointer = self._rows.one(
            "registry.release_scope_pointer",
            where={"scope_type": "SESSION", "scope_key": scope_key},
            columns=("current_release_id", "version_token"),
        )
        actual_version = (
            0
            if pointer is None
            else _required_int(
                pointer["version_token"],
                "release_scope_pointer.version_token",
            )
        )
        if actual_version != expected_version_token:
            raise P2ReleaseError(
                "P2_RELEASE_CAS_CONFLICT",
                f"expected={expected_version_token} actual={actual_version}",
            )
        parent_release_id = (
            None
            if pointer is None or pointer["current_release_id"] is None
            else str(pointer["current_release_id"])
        )
        next_version = actual_version + 1

        self._rows.insert(
            "registry.analysis_release",
            {
                "release_id": release_id,
                "scope_type": "SESSION",
                "scope_key": scope_key,
                "session_id": lineage.session_id,
                "longitudinal_scope_id": None,
                "release_no": next_version,
                "compute_job_id": job_id,
                "catalog_version": lineage.catalog_version,
                "catalog_hash": lineage.catalog_hash,
                "context_binding_hash": lineage.context_binding_hash,
                "status": "PUBLISHED",
                "parent_release_id": parent_release_id,
                "manifest_hash": manifest_hash,
                "created_at": published_at_utc,
                "published_at": published_at_utc,
            },
        )
        if pointer is None:
            self._rows.insert(
                "registry.release_scope_pointer",
                {
                    "scope_type": "SESSION",
                    "scope_key": scope_key,
                    "current_release_id": release_id,
                    "version_token": next_version,
                    "updated_at": published_at_utc,
                },
            )
        else:
            self._rows.update_exact(
                "registry.release_scope_pointer",
                where={
                    "scope_type": "SESSION",
                    "scope_key": scope_key,
                    "version_token": actual_version,
                },
                values={
                    "current_release_id": release_id,
                    "version_token": next_version,
                    "updated_at": published_at_utc,
                },
            )
        return P2PublishedRelease(
            release_id=release_id,
            scope_key=scope_key,
            session_id=lineage.session_id,
            version_token=next_version,
            parent_release_id=parent_release_id,
            manifest_hash=manifest_hash,
            reused=False,
        )
