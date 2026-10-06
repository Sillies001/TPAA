"""PRCB C3 live dependency readiness for production composition."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Protocol

from tpaa_application import GetRuntimeBaselineStatus, RuntimeBaselineStatus

from .admission import ProductFeatureAvailability

_PHASES = ("P1", "P2", "P3", "P4", "P5", "P6")


class _StorageStatus(Protocol):
    def execute(self) -> object: ...


class _CoreStatus(Protocol):
    def execute(self) -> RuntimeBaselineStatus: ...


class ProductionDependencyProbe:
    """Re-evaluate live DB/object/worker dependencies for every availability read."""

    def __init__(
        self,
        *,
        storage_status: _StorageStatus,
        object_root: Path,
        worker_handler: str = "tpaa_runtime.production_worker:execute",
    ) -> None:
        self._storage_status = storage_status
        self._object_root = object_root
        self._worker_handler = worker_handler

    def _storage_ready(self) -> bool:
        try:
            status = self._storage_status.execute()
        except Exception:
            return False
        return (
            getattr(status, "schema_version", None) == "1.9.0"
            and getattr(status, "core_baseline", None) == "CB-1.4.0"
        )

    def _object_store_ready(self) -> bool:
        root = self._object_root
        return (
            root.is_dir()
            and os.access(root, os.R_OK)
            and os.access(root, os.W_OK)
        )

    def _worker_ready(self) -> bool:
        module_name, separator, attribute = self._worker_handler.partition(":")
        if separator != ":" or not module_name or not attribute:
            return False
        try:
            module = importlib.import_module(module_name)
        except Exception:
            return False
        return callable(getattr(module, attribute, None))

    def phase_flags(self) -> dict[str, bool]:
        ready = (
            self._storage_ready()
            and self._object_store_ready()
            and self._worker_ready()
        )
        return {phase: ready for phase in _PHASES}


class ProductionRuntimeReadiness(GetRuntimeBaselineStatus):
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
