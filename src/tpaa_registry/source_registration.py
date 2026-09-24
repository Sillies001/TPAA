"""M1-DATA-002 immutable Source Registry registration primitives.

This module creates deterministic, immutable registration identities for the
controlled M1 synthetic source bundle and its fixture context file. It does not
persist registry rows and does not execute Session Time, Canonical, Context,
Stage, World, or Metric semantics owned by later M1 tasks.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid5

from tpaa_ingest import (
    GOVERNED_FIXTURE_IDS,
    SyntheticSourceAdapterError,
    load_synthetic_fixture_bundle,
)

EXPECTED_CONTEXT_SCHEMA = "TPAA_M1_SYNTHETIC_CONTEXT_V1"
EXPECTED_CLASSIFICATION = "SYNTHETIC"
EXPECTED_SOURCE_PATH = Path("source/flight.json")
EXPECTED_CONTEXT_PATH = Path("context/evaluation-context.json")
REGISTRATION_NAMESPACE = UUID("c4544e34-3cf3-4f41-9dd6-b91990d261ef")


class SourceRegistryError(RuntimeError):
    """Deterministic fail-closed Source Registry registration error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ImmutableHashRef:
    """Immutable logical identity bound to one SHA-256 digest."""

    logical_ref: str
    sha256: str
    immutable: bool = True


@dataclass(frozen=True)
class ImmutableArtifactFileRef:
    """Immutable file artifact identity used by later persistence adapters."""

    object_id: str
    logical_ref: str
    sha256: str
    managed_uri: str
    media_type: str
    size_bytes: int
    immutable: bool = True


@dataclass(frozen=True)
class SourceRegistryRegistration:
    """Prepared registration for one governed M1 source fixture."""

    fixture_id: str
    fixture_version: str
    session_id: str
    source_id: str
    source_stream_id: str
    source_time_basis: str
    bundle_ref: ImmutableHashRef
    source_artifact: ImmutableArtifactFileRef
    context_artifact: ImmutableArtifactFileRef
    context_version: str
    persistence_executed: bool = False
    canonical_context_artifact_row_executed: bool = False


class SourceRegistryIndex:
    """In-memory immutable registry index for M1-DATA-002 acceptance."""

    def __init__(self) -> None:
        self._hashes: dict[str, str] = {}

    def register(self, registration: SourceRegistryRegistration) -> None:
        refs = (
            registration.bundle_ref,
            ImmutableHashRef(
                logical_ref=registration.source_artifact.logical_ref,
                sha256=registration.source_artifact.sha256,
            ),
            ImmutableHashRef(
                logical_ref=registration.context_artifact.logical_ref,
                sha256=registration.context_artifact.sha256,
            ),
        )
        for ref in refs:
            existing = self._hashes.get(ref.logical_ref)
            if existing is not None and existing != ref.sha256:
                raise SourceRegistryError(
                    "M1_SOURCE_REGISTRY_REF_COLLISION",
                    (
                        f"ref={ref.logical_ref} "
                        f"existing_sha256={existing} new_sha256={ref.sha256}"
                    ),
                )
            self._hashes[ref.logical_ref] = ref.sha256

    def resolve_sha256(self, logical_ref: str) -> str:
        try:
            return self._hashes[logical_ref]
        except KeyError as exc:
            raise SourceRegistryError(
                "M1_SOURCE_REGISTRY_REF_UNKNOWN",
                logical_ref,
            ) from exc

    @property
    def ref_count(self) -> int:
        return len(self._hashes)


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError as exc:
        raise SourceRegistryError(
            "M1_SOURCE_REGISTRY_ARTIFACT_MISSING",
            path.as_posix(),
        ) from exc


def _load_json(path: Path) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SourceRegistryError(
            "M1_SOURCE_REGISTRY_ARTIFACT_MISSING",
            path.as_posix(),
        ) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SourceRegistryError(
            "M1_SOURCE_REGISTRY_ARTIFACT_CORRUPT",
            f"{path.as_posix()}: {exc}",
        ) from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise SourceRegistryError(
            "M1_SOURCE_REGISTRY_ARTIFACT_CORRUPT",
            f"{path.as_posix()}: JSON root must be string-keyed object",
        )
    return dict(raw)


def _required_str(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise SourceRegistryError(
            "M1_SOURCE_REGISTRY_CONTEXT_INVALID",
            f"{key} must be non-empty string",
        )
    return value


def _stable_uuid(label: str) -> str:
    return str(uuid5(REGISTRATION_NAMESPACE, label))


def _managed_uri(fixture_id: str, fixture_version: str, relative: Path) -> str:
    suffix = relative.as_posix()
    return f"m1-fixture://{fixture_id}/{fixture_version}/{suffix}"


def register_synthetic_fixture(bundle_path: Path) -> SourceRegistryRegistration:
    """Create deterministic immutable refs for one governed fixture bundle."""

    try:
        bundle = load_synthetic_fixture_bundle(bundle_path)
    except SyntheticSourceAdapterError as exc:
        raise SourceRegistryError(
            "M1_SOURCE_REGISTRY_SOURCE_REJECTED",
            f"{exc.code}: {exc.detail}",
        ) from exc

    if bundle.identity.fixture_id not in GOVERNED_FIXTURE_IDS:
        raise SourceRegistryError(
            "M1_SOURCE_REGISTRY_FIXTURE_NOT_GOVERNED",
            bundle.identity.fixture_id,
        )

    source_path = bundle_path / EXPECTED_SOURCE_PATH
    context_path = bundle_path / EXPECTED_CONTEXT_PATH
    source_sha256 = _sha256_file(source_path)
    context_sha256 = _sha256_file(context_path)
    if source_sha256 != bundle.identity.source_sha256:
        raise SourceRegistryError(
            "M1_SOURCE_REGISTRY_SOURCE_HASH_MISMATCH",
            f"expected={bundle.identity.source_sha256} actual={source_sha256}",
        )
    if context_sha256 != bundle.identity.context_sha256:
        raise SourceRegistryError(
            "M1_SOURCE_REGISTRY_CONTEXT_HASH_MISMATCH",
            f"expected={bundle.identity.context_sha256} actual={context_sha256}",
        )

    context = _load_json(context_path)
    if context.get("schema") != EXPECTED_CONTEXT_SCHEMA:
        raise SourceRegistryError(
            "M1_SOURCE_REGISTRY_CONTEXT_SCHEMA_MISMATCH",
            repr(context.get("schema")),
        )
    if context.get("fixture_id") != bundle.identity.fixture_id:
        raise SourceRegistryError(
            "M1_SOURCE_REGISTRY_CONTEXT_ID_MISMATCH",
            repr(context.get("fixture_id")),
        )
    if context.get("classification") != EXPECTED_CLASSIFICATION:
        raise SourceRegistryError(
            "M1_SOURCE_REGISTRY_CONTEXT_CLASSIFICATION_FORBIDDEN",
            repr(context.get("classification")),
        )
    context_version = _required_str(context, "context_version")

    fixture_id = bundle.identity.fixture_id
    fixture_version = bundle.identity.fixture_version
    bundle_ref = (
        f"M1_SOURCE_BUNDLE:{fixture_id}:{fixture_version}:"
        f"{bundle.identity.input_sha256}"
    )
    source_ref = (
        f"M1_SOURCE_ARTIFACT:{fixture_id}:{fixture_version}:"
        f"{source_sha256}"
    )
    context_ref = (
        f"M1_CONTEXT_FILE:{fixture_id}:{context_version}:"
        f"{context_sha256}"
    )

    return SourceRegistryRegistration(
        fixture_id=fixture_id,
        fixture_version=fixture_version,
        session_id=bundle.session.session_id,
        source_id=_stable_uuid(f"data-source|{bundle_ref}"),
        source_stream_id=_stable_uuid(f"source-stream|{bundle_ref}|PRIMARY"),
        source_time_basis=bundle.session.source_time_basis,
        bundle_ref=ImmutableHashRef(
            logical_ref=bundle_ref,
            sha256=bundle.identity.input_sha256,
        ),
        source_artifact=ImmutableArtifactFileRef(
            object_id=_stable_uuid(f"source-artifact|{source_ref}"),
            logical_ref=source_ref,
            sha256=source_sha256,
            managed_uri=_managed_uri(
                fixture_id,
                fixture_version,
                EXPECTED_SOURCE_PATH,
            ),
            media_type="application/json",
            size_bytes=source_path.stat().st_size,
        ),
        context_artifact=ImmutableArtifactFileRef(
            object_id=_stable_uuid(f"context-object|{context_ref}"),
            logical_ref=context_ref,
            sha256=context_sha256,
            managed_uri=_managed_uri(
                fixture_id,
                fixture_version,
                EXPECTED_CONTEXT_PATH,
            ),
            media_type="application/json",
            size_bytes=context_path.stat().st_size,
        ),
        context_version=context_version,
    )


def register_all_synthetic_fixtures(
    fixture_root: Path,
) -> tuple[SourceRegistryIndex, tuple[SourceRegistryRegistration, ...]]:
    """Register all eight governed M1 fixture identities into one immutable index."""

    registrations = tuple(
        register_synthetic_fixture(fixture_root / fixture_id)
        for fixture_id in sorted(GOVERNED_FIXTURE_IDS)
    )
    index = SourceRegistryIndex()
    for registration in registrations:
        index.register(registration)
    return index, registrations
