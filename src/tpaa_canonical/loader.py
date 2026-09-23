"""Fail-closed loader for frozen TPAA Canonical artifacts.

The Canonical JSON files remain the machine authority.  This module does not
restate their business schemas.  It verifies the repository trust boundary
(BASELINE_LOCK plus exact bytes) and exposes explicit consumer expectations for
artifact version/schema compatibility.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

EXPECTED_CORE_BASELINE = "CB-1.4.0"
EXPECTED_BASELINE_LOCK_SHA256 = (
    "9d96a7eb0ba2b1fb13b11d76943171f773fd42497df74bf79c01928cfa26e7fa"
)
EXPECTED_CONTROLLED_ARTIFACT_COUNT = 21
UNVERSIONED_BY_AUTHORITY = "UNVERSIONED_BY_AUTHORITY"
UNTRUSTED_NOT_PARSED = "UNTRUSTED_NOT_PARSED"
NOT_REQUESTED = "NOT_REQUESTED"

_ARTIFACT_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_VERSION_KEYS = ("version", "catalog_version", "matrix_version")
_IDENTITY_KEYS = ("registry_id", "authority_id", "provenance_id")


@dataclass(frozen=True)
class ArtifactExpectation:
    """Consumer-side compatibility requirements for one controlled artifact.

    Expectations are implementation compatibility constraints, not Canonical
    authority.  Callers should request only constraints they actually depend on.
    """

    version: str | None = None
    schema_version: str | None = None
    required_top_level_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class CanonicalArtifact:
    """Verified Canonical artifact plus immutable loader metadata."""

    artifact_id: str
    filename: str
    declared_id: str | None
    declared_version: str | None
    schema_version: str | None
    core_baseline: str | None
    sha256: str
    byte_size: int
    baseline_lock_sha256: str
    payload: Mapping[str, Any]

    @property
    def version_label(self) -> str:
        return self.declared_version or UNVERSIONED_BY_AUTHORITY


class CanonicalArtifactError(RuntimeError):
    """Deterministic fail-closed Canonical loader error.

    ``reason`` values are engineering diagnostics only; they are not TPAA
    business-status or metric reason codes.
    """

    def __init__(
        self,
        *,
        reason: str,
        artifact_id: str,
        expected_version: str | None = None,
        actual_version: str | None = None,
        expected_schema_version: str | None = None,
        actual_schema_version: str | None = None,
        detail: str,
    ) -> None:
        self.reason = reason
        self.artifact_id = artifact_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        self.expected_schema_version = expected_schema_version
        self.actual_schema_version = actual_schema_version
        self.detail = detail
        super().__init__(self._message())

    def _message(self) -> str:
        expected_version = self.expected_version or NOT_REQUESTED
        actual_version = self.actual_version or UNVERSIONED_BY_AUTHORITY
        expected_schema = self.expected_schema_version or NOT_REQUESTED
        actual_schema = self.actual_schema_version or UNVERSIONED_BY_AUTHORITY
        return (
            "CANONICAL_ARTIFACT_FAIL "
            f"reason={self.reason} "
            f"artifact_id={self.artifact_id} "
            f"version_expected={expected_version} "
            f"version_actual={actual_version} "
            f"schema_expected={expected_schema} "
            f"schema_actual={actual_schema} "
            f"detail={self.detail}"
        )


@dataclass(frozen=True)
class _LockEntry:
    artifact_id: str
    filename: str
    sha256: str
    byte_size: int


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_baseline_root() -> Path:
    return _repo_root() / "baseline" / EXPECTED_CORE_BASELINE


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_bytes(path: Path, artifact_id: str, expected_version: str | None) -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise CanonicalArtifactError(
            reason="MISSING_CONTROLLED_ARTIFACT",
            artifact_id=artifact_id,
            expected_version=expected_version,
            actual_version=UNTRUSTED_NOT_PARSED,
            detail=f"missing controlled file {path.name}",
        ) from exc
    except OSError as exc:
        raise CanonicalArtifactError(
            reason="ARTIFACT_READ_ERROR",
            artifact_id=artifact_id,
            expected_version=expected_version,
            actual_version=UNTRUSTED_NOT_PARSED,
            detail=f"cannot read {path.name}: {exc}",
        ) from exc


def _require_object(value: Any, *, artifact_id: str, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CanonicalArtifactError(
            reason="SCHEMA_MISMATCH",
            artifact_id=artifact_id,
            detail=f"{context} must be a JSON object",
        )
    return value


def _string_field(payload: Mapping[str, Any], keys: Iterable[str]) -> tuple[str | None, str | None]:
    for key in keys:
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, str) and value:
            return key, value
        return key, None
    return None, None


class CanonicalArtifactLoader:
    """Load only artifacts controlled by the approved CB-1.4.0 baseline lock."""

    def __init__(
        self,
        baseline_root: Path | None = None,
        *,
        expected_core_baseline: str = EXPECTED_CORE_BASELINE,
        trusted_lock_sha256: str = EXPECTED_BASELINE_LOCK_SHA256,
    ) -> None:
        self.baseline_root = (baseline_root or _default_baseline_root()).resolve()
        self.canonical_root = self.baseline_root / "canonical"
        self.expected_core_baseline = expected_core_baseline
        self.trusted_lock_sha256 = trusted_lock_sha256.lower()
        self._baseline_metadata, self._entries = self._load_and_verify_lock()

    @property
    def baseline_metadata(self) -> Mapping[str, Any]:
        return MappingProxyType(dict(self._baseline_metadata))

    @property
    def artifact_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def _load_and_verify_lock(self) -> tuple[dict[str, Any], dict[str, _LockEntry]]:
        lock_path = self.baseline_root / "BASELINE_LOCK.json"
        try:
            lock_bytes = lock_path.read_bytes()
        except OSError as exc:
            raise CanonicalArtifactError(
                reason="BASELINE_LOCK_READ_ERROR",
                artifact_id="BASELINE_LOCK",
                actual_version=UNTRUSTED_NOT_PARSED,
                detail=f"cannot read BASELINE_LOCK.json: {exc}",
            ) from exc

        actual_lock_hash = _sha256_bytes(lock_bytes)
        if actual_lock_hash != self.trusted_lock_sha256:
            raise CanonicalArtifactError(
                reason="BASELINE_LOCK_HASH_MISMATCH",
                artifact_id="BASELINE_LOCK",
                actual_version=UNTRUSTED_NOT_PARSED,
                detail=(
                    f"expected_sha256={self.trusted_lock_sha256} "
                    f"actual_sha256={actual_lock_hash}"
                ),
            )

        try:
            raw_lock = json.loads(lock_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CanonicalArtifactError(
                reason="BASELINE_LOCK_INVALID_JSON",
                artifact_id="BASELINE_LOCK",
                actual_version=UNTRUSTED_NOT_PARSED,
                detail=str(exc),
            ) from exc
        lock = _require_object(raw_lock, artifact_id="BASELINE_LOCK", context="BASELINE_LOCK")
        baseline = _require_object(
            lock.get("baseline"), artifact_id="BASELINE_LOCK", context="baseline"
        )
        core = baseline.get("core")
        if core != self.expected_core_baseline:
            raise CanonicalArtifactError(
                reason="CORE_BASELINE_MISMATCH",
                artifact_id="BASELINE_LOCK",
                actual_version=str(core) if core is not None else None,
                detail=(
                    f"expected_core={self.expected_core_baseline} actual_core={core!r}"
                ),
            )

        db_schema = baseline.get("db_schema")
        if not isinstance(db_schema, str) or not db_schema:
            raise CanonicalArtifactError(
                reason="BASELINE_LOCK_SCHEMA_MISMATCH",
                artifact_id="BASELINE_LOCK",
                detail="baseline.db_schema must be a non-empty string",
            )

        artifacts = lock.get("artifacts")
        if not isinstance(artifacts, list):
            raise CanonicalArtifactError(
                reason="BASELINE_LOCK_SCHEMA_MISMATCH",
                artifact_id="BASELINE_LOCK",
                detail="artifacts must be a JSON array",
            )
        if len(artifacts) != EXPECTED_CONTROLLED_ARTIFACT_COUNT:
            raise CanonicalArtifactError(
                reason="BASELINE_LOCK_SCHEMA_MISMATCH",
                artifact_id="BASELINE_LOCK",
                detail=(
                    "controlled artifact count mismatch "
                    f"expected={EXPECTED_CONTROLLED_ARTIFACT_COUNT} actual={len(artifacts)}"
                ),
            )

        entries: dict[str, _LockEntry] = {}
        for raw_entry in artifacts:
            entry = _require_object(
                raw_entry, artifact_id="BASELINE_LOCK", context="artifacts entry"
            )
            filename = entry.get("file")
            digest = entry.get("sha256")
            byte_size = entry.get("bytes")
            if not isinstance(filename, str) or Path(filename).name != filename:
                raise CanonicalArtifactError(
                    reason="BASELINE_LOCK_SCHEMA_MISMATCH",
                    artifact_id="BASELINE_LOCK",
                    detail=f"unsafe or invalid artifact filename {filename!r}",
                )
            if not filename.endswith(".json"):
                raise CanonicalArtifactError(
                    reason="BASELINE_LOCK_SCHEMA_MISMATCH",
                    artifact_id="BASELINE_LOCK",
                    detail=f"controlled artifact must be JSON: {filename}",
                )
            artifact_id = filename.removesuffix(".json")
            if not _ARTIFACT_ID_RE.fullmatch(artifact_id):
                raise CanonicalArtifactError(
                    reason="BASELINE_LOCK_SCHEMA_MISMATCH",
                    artifact_id="BASELINE_LOCK",
                    detail=f"invalid controlled artifact id {artifact_id!r}",
                )
            if not isinstance(digest, str) or len(digest) != 64:
                raise CanonicalArtifactError(
                    reason="BASELINE_LOCK_SCHEMA_MISMATCH",
                    artifact_id=artifact_id,
                    detail="sha256 must be a 64-character string",
                )
            try:
                int(digest, 16)
            except ValueError as exc:
                raise CanonicalArtifactError(
                    reason="BASELINE_LOCK_SCHEMA_MISMATCH",
                    artifact_id=artifact_id,
                    detail="sha256 must be hexadecimal",
                ) from exc
            if not isinstance(byte_size, int) or byte_size < 0:
                raise CanonicalArtifactError(
                    reason="BASELINE_LOCK_SCHEMA_MISMATCH",
                    artifact_id=artifact_id,
                    detail="bytes must be a non-negative integer",
                )
            if artifact_id in entries:
                raise CanonicalArtifactError(
                    reason="BASELINE_LOCK_SCHEMA_MISMATCH",
                    artifact_id=artifact_id,
                    detail="duplicate controlled artifact id",
                )
            entries[artifact_id] = _LockEntry(
                artifact_id=artifact_id,
                filename=filename,
                sha256=digest.lower(),
                byte_size=byte_size,
            )

        if not self.canonical_root.is_dir():
            raise CanonicalArtifactError(
                reason="MISSING_CANONICAL_ROOT",
                artifact_id="BASELINE_LOCK",
                detail=f"missing canonical directory {self.canonical_root}",
            )
        listed = {entry.filename for entry in entries.values()}
        present = {path.name for path in self.canonical_root.glob("*.json") if path.is_file()}
        unexpected = sorted(present - listed)
        if unexpected:
            raise CanonicalArtifactError(
                reason="UNCONTROLLED_CANONICAL_ARTIFACT",
                artifact_id="BASELINE_LOCK",
                detail="unexpected canonical JSON: " + ", ".join(unexpected),
            )
        return baseline, entries

    @staticmethod
    def _normalize_artifact_id(artifact_id: str) -> str:
        normalized = artifact_id.removesuffix(".json")
        if not _ARTIFACT_ID_RE.fullmatch(normalized):
            raise CanonicalArtifactError(
                reason="INVALID_ARTIFACT_ID",
                artifact_id=artifact_id,
                detail="artifact id must match ^[A-Z][A-Z0-9_]*$",
            )
        return normalized

    def load(
        self,
        artifact_id: str,
        *,
        expectation: ArtifactExpectation | None = None,
    ) -> CanonicalArtifact:
        """Load one verified Canonical artifact or fail closed."""

        normalized_id = self._normalize_artifact_id(artifact_id)
        expected = expectation or ArtifactExpectation()
        entry = self._entries.get(normalized_id)
        if entry is None:
            raise CanonicalArtifactError(
                reason="UNKNOWN_ARTIFACT",
                artifact_id=normalized_id,
                expected_version=expected.version,
                actual_version=UNTRUSTED_NOT_PARSED,
                expected_schema_version=expected.schema_version,
                detail="artifact is not controlled by BASELINE_LOCK.json",
            )

        artifact_path = self.canonical_root / entry.filename
        artifact_bytes = _read_bytes(artifact_path, normalized_id, expected.version)
        actual_size = len(artifact_bytes)
        actual_hash = _sha256_bytes(artifact_bytes)
        if actual_size != entry.byte_size or actual_hash != entry.sha256:
            raise CanonicalArtifactError(
                reason="CONTROLLED_ARTIFACT_DRIFT",
                artifact_id=normalized_id,
                expected_version=expected.version,
                actual_version=UNTRUSTED_NOT_PARSED,
                expected_schema_version=expected.schema_version,
                detail=(
                    f"expected_bytes={entry.byte_size} actual_bytes={actual_size} "
                    f"expected_sha256={entry.sha256} actual_sha256={actual_hash}"
                ),
            )

        try:
            raw_payload = json.loads(artifact_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CanonicalArtifactError(
                reason="INVALID_JSON",
                artifact_id=normalized_id,
                expected_version=expected.version,
                actual_version=UNTRUSTED_NOT_PARSED,
                expected_schema_version=expected.schema_version,
                detail=str(exc),
            ) from exc
        payload = _require_object(
            raw_payload, artifact_id=normalized_id, context="Canonical artifact"
        )

        identity_key, declared_id = _string_field(payload, _IDENTITY_KEYS)
        if identity_key is not None and declared_id is None:
            raise CanonicalArtifactError(
                reason="SCHEMA_MISMATCH",
                artifact_id=normalized_id,
                expected_version=expected.version,
                expected_schema_version=expected.schema_version,
                detail=f"{identity_key} must be a non-empty string",
            )

        version_key, declared_version = _string_field(payload, _VERSION_KEYS)
        if version_key is not None and declared_version is None:
            raise CanonicalArtifactError(
                reason="SCHEMA_MISMATCH",
                artifact_id=normalized_id,
                expected_version=expected.version,
                expected_schema_version=expected.schema_version,
                detail=f"{version_key} must be a non-empty string",
            )

        schema_version_raw = payload.get("db_schema_version")
        schema_version: str | None
        if schema_version_raw is None:
            schema_version = None
        elif isinstance(schema_version_raw, str) and schema_version_raw:
            schema_version = schema_version_raw
        else:
            raise CanonicalArtifactError(
                reason="SCHEMA_MISMATCH",
                artifact_id=normalized_id,
                expected_version=expected.version,
                actual_version=declared_version,
                expected_schema_version=expected.schema_version,
                detail="db_schema_version must be a non-empty string when declared",
            )

        core_raw = payload.get("core_baseline")
        core_baseline: str | None
        if core_raw is None:
            core_baseline = None
        elif isinstance(core_raw, str) and core_raw:
            core_baseline = core_raw
        else:
            raise CanonicalArtifactError(
                reason="SCHEMA_MISMATCH",
                artifact_id=normalized_id,
                expected_version=expected.version,
                actual_version=declared_version,
                expected_schema_version=expected.schema_version,
                actual_schema_version=schema_version,
                detail="core_baseline must be a non-empty string when declared",
            )

        if core_baseline is not None and core_baseline != self.expected_core_baseline:
            raise CanonicalArtifactError(
                reason="CORE_BASELINE_MISMATCH",
                artifact_id=normalized_id,
                expected_version=expected.version,
                actual_version=declared_version,
                expected_schema_version=expected.schema_version,
                actual_schema_version=schema_version,
                detail=(
                    f"expected_core={self.expected_core_baseline} actual_core={core_baseline}"
                ),
            )

        lock_schema = self._baseline_metadata.get("db_schema")
        if schema_version is not None and schema_version != lock_schema:
            raise CanonicalArtifactError(
                reason="SCHEMA_VERSION_MISMATCH",
                artifact_id=normalized_id,
                expected_version=expected.version,
                actual_version=declared_version,
                expected_schema_version=(
                    str(lock_schema) if lock_schema is not None else expected.schema_version
                ),
                actual_schema_version=schema_version,
                detail="artifact db_schema_version disagrees with BASELINE_LOCK baseline metadata",
            )

        if expected.version is not None:
            if declared_version is None:
                raise CanonicalArtifactError(
                    reason="VERSION_UNDECLARED",
                    artifact_id=normalized_id,
                    expected_version=expected.version,
                    actual_version=UNVERSIONED_BY_AUTHORITY,
                    expected_schema_version=expected.schema_version,
                    actual_schema_version=schema_version,
                    detail=(
                        "consumer requires a version but authority declares no "
                        "artifact version field"
                    ),
                )
            if declared_version != expected.version:
                raise CanonicalArtifactError(
                    reason="VERSION_MISMATCH",
                    artifact_id=normalized_id,
                    expected_version=expected.version,
                    actual_version=declared_version,
                    expected_schema_version=expected.schema_version,
                    actual_schema_version=schema_version,
                    detail="consumer-supported artifact version does not match authority",
                )

        if expected.schema_version is not None:
            if schema_version is None:
                raise CanonicalArtifactError(
                    reason="SCHEMA_VERSION_UNDECLARED",
                    artifact_id=normalized_id,
                    expected_version=expected.version,
                    actual_version=declared_version,
                    expected_schema_version=expected.schema_version,
                    actual_schema_version=UNVERSIONED_BY_AUTHORITY,
                    detail="consumer requires db_schema_version but authority does not declare one",
                )
            if schema_version != expected.schema_version:
                raise CanonicalArtifactError(
                    reason="SCHEMA_VERSION_MISMATCH",
                    artifact_id=normalized_id,
                    expected_version=expected.version,
                    actual_version=declared_version,
                    expected_schema_version=expected.schema_version,
                    actual_schema_version=schema_version,
                    detail="consumer-supported schema version does not match authority",
                )

        missing_keys = sorted(
            key for key in expected.required_top_level_keys if key not in payload
        )
        if missing_keys:
            raise CanonicalArtifactError(
                reason="SCHEMA_MISMATCH",
                artifact_id=normalized_id,
                expected_version=expected.version,
                actual_version=declared_version,
                expected_schema_version=expected.schema_version,
                actual_schema_version=schema_version,
                detail="missing required top-level keys: " + ", ".join(missing_keys),
            )

        return CanonicalArtifact(
            artifact_id=normalized_id,
            filename=entry.filename,
            declared_id=declared_id,
            declared_version=declared_version,
            schema_version=schema_version,
            core_baseline=core_baseline,
            sha256=actual_hash,
            byte_size=actual_size,
            baseline_lock_sha256=self.trusted_lock_sha256,
            payload=MappingProxyType(payload),
        )

    def load_all(
        self,
        expectations: Mapping[str, ArtifactExpectation] | None = None,
    ) -> tuple[CanonicalArtifact, ...]:
        """Load all controlled artifacts in deterministic artifact-id order."""

        requested = expectations or {}
        unknown_expectations = sorted(set(requested) - set(self._entries))
        if unknown_expectations:
            unknown = unknown_expectations[0]
            raise CanonicalArtifactError(
                reason="UNKNOWN_ARTIFACT",
                artifact_id=unknown,
                detail="expectation references an artifact not controlled by BASELINE_LOCK.json",
            )
        return tuple(
            self.load(artifact_id, expectation=requested.get(artifact_id))
            for artifact_id in self.artifact_ids
        )
