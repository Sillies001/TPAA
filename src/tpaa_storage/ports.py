"""Engine-neutral Repository and Unit-of-Work contracts frozen by ADR-M0-004."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RepositoryBaselineMetadata:
    """Schema/baseline provenance visible through the Repository boundary."""

    engine_profile: str
    schema_version: str
    core_baseline: str
    authority_artifact_id: str
    authority_sha256: str
    baseline_lock_sha256: str
    physical_schema_sha256: str


@runtime_checkable
class BaselineMetadataRepository(Protocol):
    """Read-only access to persisted bootstrap provenance."""

    def get(self) -> RepositoryBaselineMetadata:
        """Return the singleton persisted schema/baseline metadata."""


@runtime_checkable
class RepositoryUnitOfWork(Protocol):
    """Engine-neutral explicit transaction boundary."""

    metadata: BaselineMetadataRepository

    def __enter__(self) -> RepositoryUnitOfWork:
        """Open exactly one adapter connection/transaction."""

    def commit(self) -> None:
        """Explicitly commit the active transaction."""

    def rollback(self) -> None:
        """Explicitly roll back the active transaction."""

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        """Roll back any transaction not already finalized."""
