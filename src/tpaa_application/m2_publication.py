"""Idempotent publication and explicit historical replay for M2 Releases.

M2-OBS-003 provides the application/repository semantics over immutable
M2-OBS-002 Release snapshots. Historical reads are release-id bound; the
reference repository never consults current/latest Catalog, Profile, Context,
or World state when reading or comparing a historical Release.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from tpaa_observation import M2ImmutableReleaseSnapshot


class M2PublicationError(RuntimeError):
    """Base deterministic M2 publication failure."""


class M2PublishCASConflict(M2PublicationError):
    def __init__(self, *, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"M2_PUBLISH_CAS_CONFLICT expected={expected} actual={actual}"
        )


class M2PublishIdempotencyConflict(M2PublicationError):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"M2_PUBLISH_IDEMPOTENCY_CONFLICT key={key}")


class M2PublishedReleaseConflict(M2PublicationError):
    def __init__(self, release_id: str) -> None:
        self.release_id = release_id
        super().__init__(f"M2_PUBLISHED_RELEASE_CONFLICT release_id={release_id}")


class M2ReleaseNotFound(M2PublicationError):
    def __init__(self, release_id: str) -> None:
        self.release_id = release_id
        super().__init__(f"M2_RELEASE_NOT_FOUND release_id={release_id}")


@dataclass(frozen=True)
class M2PublishedRelease:
    release: M2ImmutableReleaseSnapshot
    version_token: int
    status: str = "PUBLISHED"

    def __post_init__(self) -> None:
        if self.status != "PUBLISHED":
            raise M2PublicationError(
                f"M2_INVALID_PUBLISHED_STATUS status={self.status}"
            )
        if self.version_token < 1:
            raise M2PublicationError(
                "M2_INVALID_PUBLISHED_VERSION_TOKEN "
                f"token={self.version_token}"
            )


@dataclass(frozen=True)
class M2PublishResult:
    published: M2PublishedRelease
    reused: bool


@dataclass(frozen=True)
class M2ReplayComparison:
    release_id: str
    release_identity_equal: bool
    manifest_equal: bool
    catalog_equal: bool
    plan_equal: bool
    routing_equal: bool
    execution_equal: bool
    bindings_equal: bool
    definitions_equal: bool
    execution_records_equal: bool
    exact_logical_products_equal: bool


def compare_m2_release_replay(
    release: M2ImmutableReleaseSnapshot,
    candidate: M2ImmutableReleaseSnapshot,
) -> M2ReplayComparison:
    """Compare explicit immutable Release products without resolving latest state."""

    release_identity_equal = (
        release.release_id == candidate.release_id
        and release.release_no == candidate.release_no
        and release.parent_release_id == candidate.parent_release_id
        and release.session_id == candidate.session_id
        and release.request_hash == candidate.request_hash
    )
    manifest_equal = release.manifest_hash == candidate.manifest_hash
    catalog_equal = (
        release.catalog_id == candidate.catalog_id
        and release.catalog_version == candidate.catalog_version
        and release.catalog_hash == candidate.catalog_hash
    )
    plan_equal = (
        release.metric_execution_plan_hash
        == candidate.metric_execution_plan_hash
    )
    routing_equal = (
        release.publication_routing_plan_hash
        == candidate.publication_routing_plan_hash
    )
    execution_equal = (
        release.execution_batch_hash == candidate.execution_batch_hash
        and release.plugin_manifest_hash == candidate.plugin_manifest_hash
    )
    bindings_equal = release.bindings == candidate.bindings
    definitions_equal = release.definitions == candidate.definitions
    execution_records_equal = (
        release.execution_records == candidate.execution_records
    )
    exact = all(
        (
            release_identity_equal,
            manifest_equal,
            catalog_equal,
            plan_equal,
            routing_equal,
            execution_equal,
            bindings_equal,
            definitions_equal,
            execution_records_equal,
        )
    )
    return M2ReplayComparison(
        release_id=release.release_id,
        release_identity_equal=release_identity_equal,
        manifest_equal=manifest_equal,
        catalog_equal=catalog_equal,
        plan_equal=plan_equal,
        routing_equal=routing_equal,
        execution_equal=execution_equal,
        bindings_equal=bindings_equal,
        definitions_equal=definitions_equal,
        execution_records_equal=execution_records_equal,
        exact_logical_products_equal=exact,
    )


@runtime_checkable
class M2ReleasePublicationRepository(Protocol):
    def idempotency_lookup(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
    ) -> M2PublishedRelease | None:
        """Resolve one exact prior request by key, or fail on key reuse."""

    def publish(
        self,
        release: M2ImmutableReleaseSnapshot,
        *,
        idempotency_key: str,
        expected_version_token: int,
    ) -> M2PublishResult:
        """CAS-publish one immutable release."""

    def get_release(self, release_id: str) -> M2PublishedRelease:
        """Read one explicit historical Release; never current/latest fallback."""

    def current(self, session_id: str) -> M2PublishedRelease | None:
        """Read the mutable current pointer for new publication only."""

    def version_token(self, session_id: str) -> int:
        """Read the current SESSION CAS token."""


class InMemoryM2ReleasePublicationRepository:
    """Thread-safe executable reference semantics for M2 publication."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._releases: dict[str, M2PublishedRelease] = {}
        self._current: dict[str, str] = {}
        self._tokens: dict[str, int] = {}
        self._idempotency: dict[str, tuple[str, str, str]] = {}

    @staticmethod
    def _require_key(idempotency_key: str) -> str:
        key = idempotency_key.strip()
        if not key:
            raise M2PublicationError("M2_IDEMPOTENCY_KEY_REQUIRED")
        return key

    def idempotency_lookup(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
    ) -> M2PublishedRelease | None:
        key = self._require_key(idempotency_key)
        with self._lock:
            prior = self._idempotency.get(key)
            if prior is None:
                return None
            prior_request_hash, _, release_id = prior
            if prior_request_hash != request_hash:
                raise M2PublishIdempotencyConflict(key)
            return self._releases[release_id]

    def publish(
        self,
        release: M2ImmutableReleaseSnapshot,
        *,
        idempotency_key: str,
        expected_version_token: int,
    ) -> M2PublishResult:
        key = self._require_key(idempotency_key)
        if expected_version_token < 0:
            raise M2PublicationError(
                "M2_EXPECTED_VERSION_TOKEN_INVALID "
                f"token={expected_version_token}"
            )

        with self._lock:
            prior = self._idempotency.get(key)
            if prior is not None:
                prior_request_hash, prior_manifest_hash, prior_release_id = prior
                if (
                    prior_request_hash != release.request_hash
                    or prior_manifest_hash != release.manifest_hash
                    or prior_release_id != release.release_id
                ):
                    raise M2PublishIdempotencyConflict(key)
                return M2PublishResult(
                    published=self._releases[prior_release_id],
                    reused=True,
                )

            session_id = release.session_id
            actual_token = self._tokens.get(session_id, 0)
            if actual_token != expected_version_token:
                raise M2PublishCASConflict(
                    expected=expected_version_token,
                    actual=actual_token,
                )

            expected_parent = self._current.get(session_id)
            expected_release_no = actual_token + 1
            if release.parent_release_id != expected_parent:
                raise M2PublicationError(
                    "M2_PUBLISH_PARENT_RELEASE_MISMATCH "
                    f"expected={expected_parent!r} "
                    f"actual={release.parent_release_id!r}"
                )
            if release.release_no != expected_release_no:
                raise M2PublicationError(
                    "M2_PUBLISH_RELEASE_NO_MISMATCH "
                    f"expected={expected_release_no} "
                    f"actual={release.release_no}"
                )

            existing = self._releases.get(release.release_id)
            if existing is not None:
                if existing.release.manifest_hash != release.manifest_hash:
                    raise M2PublishedReleaseConflict(release.release_id)
                self._idempotency[key] = (
                    release.request_hash,
                    release.manifest_hash,
                    release.release_id,
                )
                return M2PublishResult(published=existing, reused=True)

            next_token = actual_token + 1
            published = M2PublishedRelease(
                release=release,
                version_token=next_token,
            )
            self._releases[release.release_id] = published
            self._current[session_id] = release.release_id
            self._tokens[session_id] = next_token
            self._idempotency[key] = (
                release.request_hash,
                release.manifest_hash,
                release.release_id,
            )
            return M2PublishResult(published=published, reused=False)

    def get_release(self, release_id: str) -> M2PublishedRelease:
        with self._lock:
            published = self._releases.get(release_id)
        if published is None:
            raise M2ReleaseNotFound(release_id)
        return published

    def current(self, session_id: str) -> M2PublishedRelease | None:
        with self._lock:
            release_id = self._current.get(session_id)
            if release_id is None:
                return None
            return self._releases[release_id]

    def version_token(self, session_id: str) -> int:
        with self._lock:
            return self._tokens.get(session_id, 0)


class M2PublicationService:
    """Application facade that keeps historical reads explicitly Release-bound."""

    def __init__(self, repository: M2ReleasePublicationRepository) -> None:
        self._repository = repository

    def publish(
        self,
        release: M2ImmutableReleaseSnapshot,
        *,
        idempotency_key: str,
        expected_version_token: int,
    ) -> M2PublishResult:
        return self._repository.publish(
            release,
            idempotency_key=idempotency_key,
            expected_version_token=expected_version_token,
        )

    def historical_release(self, release_id: str) -> M2PublishedRelease:
        return self._repository.get_release(release_id)

    def current(self, session_id: str) -> M2PublishedRelease | None:
        return self._repository.current(session_id)

    def replay(
        self,
        release_id: str,
        candidate: M2ImmutableReleaseSnapshot,
    ) -> M2ReplayComparison:
        historical = self._repository.get_release(release_id)
        return compare_m2_release_replay(historical.release, candidate)
