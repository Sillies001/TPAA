"""Engine-neutral M1 SESSION publication repository contract and reference model."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from tpaa_observation import SessionRelease


class PublicationRepositoryError(RuntimeError):
    """Base deterministic publication repository failure."""


class PublishCASConflict(PublicationRepositoryError):
    def __init__(self, *, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(f"PUBLISH_CAS_CONFLICT expected={expected} actual={actual}")


class PublishIdempotencyConflict(PublicationRepositoryError):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"PUBLISH_IDEMPOTENCY_CONFLICT key={key}")


class PublishedReleaseConflict(PublicationRepositoryError):
    def __init__(self, release_id: str) -> None:
        self.release_id = release_id
        super().__init__(f"PUBLISHED_RELEASE_CONFLICT release_id={release_id}")


class ReleaseNotFound(PublicationRepositoryError):
    def __init__(self, release_id: str) -> None:
        self.release_id = release_id
        super().__init__(f"RELEASE_NOT_FOUND release_id={release_id}")


@dataclass(frozen=True)
class PublishedSessionRelease:
    """Immutable published Release plus the CAS token that installed it."""

    release: SessionRelease
    version_token: int
    status: str = "PUBLISHED"

    def __post_init__(self) -> None:
        if self.status != "PUBLISHED":
            raise PublicationRepositoryError(f"INVALID_PUBLISHED_STATUS status={self.status}")
        if self.version_token < 1:
            raise PublicationRepositoryError(
                f"INVALID_PUBLISHED_VERSION_TOKEN token={self.version_token}"
            )


@dataclass(frozen=True)
class PublishResult:
    published: PublishedSessionRelease
    reused: bool


@runtime_checkable
class SessionPublicationRepository(Protocol):
    """Repository contract consumed by Application publication use cases."""

    def publish(
        self,
        release: SessionRelease,
        *,
        idempotency_key: str,
        expected_version_token: int,
    ) -> PublishResult:
        """CAS-publish an immutable SESSION Release."""

    def get_release(self, release_id: str) -> PublishedSessionRelease:
        """Read one explicit historical Release by immutable identity."""

    def current(self, session_id: str) -> PublishedSessionRelease | None:
        """Read the current SESSION pointer; never used for historical reads."""

    def version_token(self, session_id: str) -> int:
        """Return the current SESSION pointer CAS token."""


class InMemorySessionPublicationRepository:
    """Thread-safe reference semantics for CAS/idempotency and historical immutability."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._releases: dict[str, PublishedSessionRelease] = {}
        self._current: dict[str, str] = {}
        self._tokens: dict[str, int] = {}
        self._idempotency: dict[str, tuple[str, str, str]] = {}

    def publish(
        self,
        release: SessionRelease,
        *,
        idempotency_key: str,
        expected_version_token: int,
    ) -> PublishResult:
        if not idempotency_key.strip():
            raise ValueError("idempotency_key must be non-empty")
        if expected_version_token < 0:
            raise ValueError("expected_version_token must be >= 0")

        session_id = release.session_id
        with self._lock:
            prior_idempotency = self._idempotency.get(idempotency_key)
            if prior_idempotency is not None:
                request_hash, manifest_hash, release_id = prior_idempotency
                if (
                    request_hash != release.request_hash
                    or manifest_hash != release.manifest_hash
                    or release_id != release.release_id
                ):
                    raise PublishIdempotencyConflict(idempotency_key)
                return PublishResult(self._releases[release_id], reused=True)

            actual_token = self._tokens.get(session_id, 0)
            if actual_token != expected_version_token:
                raise PublishCASConflict(expected=expected_version_token, actual=actual_token)

            current_id = self._current.get(session_id)
            expected_parent = current_id
            expected_release_no = actual_token + 1
            if release.parent_release_id != expected_parent:
                raise PublicationRepositoryError(
                    "PUBLISH_PARENT_RELEASE_MISMATCH "
                    f"expected={expected_parent!r} actual={release.parent_release_id!r}"
                )
            if release.release_no != expected_release_no:
                raise PublicationRepositoryError(
                    "PUBLISH_RELEASE_NO_MISMATCH "
                    f"expected={expected_release_no} actual={release.release_no}"
                )

            existing = self._releases.get(release.release_id)
            if existing is not None:
                if existing.release.manifest_hash != release.manifest_hash:
                    raise PublishedReleaseConflict(release.release_id)
                self._idempotency[idempotency_key] = (
                    release.request_hash,
                    release.manifest_hash,
                    release.release_id,
                )
                return PublishResult(existing, reused=True)

            next_token = actual_token + 1
            published = PublishedSessionRelease(release=release, version_token=next_token)
            self._releases[release.release_id] = published
            self._current[session_id] = release.release_id
            self._tokens[session_id] = next_token
            self._idempotency[idempotency_key] = (
                release.request_hash,
                release.manifest_hash,
                release.release_id,
            )
            return PublishResult(published, reused=False)

    def get_release(self, release_id: str) -> PublishedSessionRelease:
        with self._lock:
            release = self._releases.get(release_id)
        if release is None:
            raise ReleaseNotFound(release_id)
        return release

    def current(self, session_id: str) -> PublishedSessionRelease | None:
        with self._lock:
            release_id = self._current.get(session_id)
            if release_id is None:
                return None
            return self._releases[release_id]

    def version_token(self, session_id: str) -> int:
        with self._lock:
            return self._tokens.get(session_id, 0)

    def logical_membership(self, release_id: str) -> dict[str, object]:
        """Return engine-neutral logical membership for parity tests."""

        return self.get_release(release_id).release.logical_membership()
