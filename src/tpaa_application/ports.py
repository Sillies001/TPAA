"""Narrow ports consumed by the Application Service."""

from __future__ import annotations

from typing import Protocol

from tpaa_storage.ports import RepositoryUnitOfWork


class RepositoryUnitOfWorkFactory(Protocol):
    """Create a fresh engine-neutral Repository unit of work per use-case invocation."""

    def __call__(self) -> RepositoryUnitOfWork:
        """Return a not-yet-entered unit of work."""
