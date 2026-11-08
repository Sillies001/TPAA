"""PRCB C3 live dependency readiness for production composition."""

from __future__ import annotations

import importlib
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from tpaa_application import RuntimeBaselineStatus
from tpaa_storage import ObjectStore

from .admission import ProductFeatureAvailability

_PHASES = ("P1", "P2", "P3", "P4", "P5", "P6")
_MIGRATION_HEAD = "1.9.0"
_CORE_BASELINE = "CB-1.5.0"


class _StorageStatus(Protocol):
    def execute(self) -> object: ...


class _CoreStatus(Protocol):
    def execute(self) -> RuntimeBaselineStatus: ...


@dataclass(frozen=True, slots=True)
class DependencyReadinessSnapshot:
    """Explicit components which must all be healthy before product READY."""

    migration_head: bool
    authority_closure: bool
    object_store: bool
    identity: bool
    worker: bool

    @property
    def ready(self) -> bool:
        return all(asdict(self).values())

    def payload(self) -> dict[str, bool]:
        return {key: bool(value) for key, value in asdict(self).items()}


class ProductionDependencyProbe:
    """Re-evaluate live DB/object/worker dependencies for every availability read."""

    def __init__(
        self,
        *,
        storage_status: _StorageStatus,
        object_root: Path,
        object_store: ObjectStore | None = None,
        worker_handler: str = "tpaa_runtime.production_worker:execute",
        identity_ready: bool | Callable[[], bool] = True,
        migration_ready: Callable[[], bool] | None = None,
        expected_schema_version: str = _MIGRATION_HEAD,
        expected_core_baseline: str = _CORE_BASELINE,
    ) -> None:
        self._storage_status = storage_status
        self._object_root = object_root
        self._object_store = object_store
        self._worker_handler = worker_handler
        self._identity_ready = identity_ready
        self._migration_ready = migration_ready
        self._expected_schema_version = expected_schema_version
        self._expected_core_baseline = expected_core_baseline

    def _storage_status_value(self) -> object | None:
        try:
            return self._storage_status.execute()
        except Exception:
            return None

    def _migration_head_ready(self, status: object | None) -> bool:
        if status is None:
            return False
        return (
            getattr(status, "schema_version", None) == self._expected_schema_version
            and getattr(status, "core_baseline", None) == self._expected_core_baseline
        )

    @staticmethod
    def _authority_ready(status: object | None) -> bool:
        if status is None:
            return False
        authority_hash = getattr(status, "authority_sha256", None)
        lock_hash = getattr(status, "baseline_lock_sha256", None)
        return (
            getattr(status, "authority_artifact_id", None) == "CORE_LOGICAL_MODEL"
            and isinstance(authority_hash, str)
            and len(authority_hash) == 64
            and isinstance(lock_hash, str)
            and len(lock_hash) == 64
        )

    def _object_store_ready(self) -> bool:
        if self._object_store is not None:
            try:
                self._object_store.ensure_ready()
            except Exception:
                return False
            return True
        root = self._object_root
        return root.is_dir() and os.access(root, os.R_OK) and os.access(root, os.W_OK)

    def _worker_ready(self) -> bool:
        module_name, separator, attribute = self._worker_handler.partition(":")
        if separator != ":" or not module_name or not attribute:
            return False
        try:
            module = importlib.import_module(module_name)
        except Exception:
            return False
        return callable(getattr(module, attribute, None))

    def _identity_provider_ready(self) -> bool:
        try:
            value = (
                self._identity_ready() if callable(self._identity_ready) else self._identity_ready
            )
        except Exception:
            return False
        return value is True

    def component_status(self) -> DependencyReadinessSnapshot:
        status = self._storage_status_value()
        migration_head = self._migration_head_ready(status)
        if self._migration_ready is not None:
            try:
                migration_head = migration_head and self._migration_ready() is True
            except Exception:
                migration_head = False
        return DependencyReadinessSnapshot(
            migration_head=migration_head,
            authority_closure=self._authority_ready(status),
            object_store=self._object_store_ready(),
            identity=self._identity_provider_ready(),
            worker=self._worker_ready(),
        )

    def phase_flags(self) -> dict[str, bool]:
        ready = self.component_status().ready
        return {phase: ready for phase in _PHASES}


class ProductionRuntimeReadiness:
    """Combine Core identity readiness with live product dependency availability."""

    def __init__(
        self,
        core_status: _CoreStatus,
        feature_availability: ProductFeatureAvailability,
    ) -> None:
        self._core_status = core_status
        self._feature_availability = feature_availability

    def execute(self) -> RuntimeBaselineStatus:
        core = self._core_status.execute()
        availability = self._feature_availability.execute()
        items = availability.get("items")
        if not isinstance(items, list):
            raise RuntimeError("production feature availability projection invalid")
        mismatches = tuple(
            f"FEATURE_{item.get('phase')}_{item.get('state')}"
            for item in items
            if isinstance(item, dict) and item.get("state") != "AVAILABLE"
        )
        if core.ready and not mismatches:
            return core
        return RuntimeBaselineStatus(
            readiness="NOT_READY",
            ready=False,
            mismatches=core.mismatches + mismatches,
            expected=core.expected,
            observed=core.observed,
        )
