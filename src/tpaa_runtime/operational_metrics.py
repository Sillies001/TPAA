"""Secret-safe, low-cardinality production operational metrics."""

from __future__ import annotations

import re
import shutil
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from time import monotonic, monotonic_ns
from typing import Protocol

from tpaa_storage import ComputeJobRepository, ComputeJobState, ObjectStore

from .config import RuntimeProfile
from .durable_repositories import RuntimeUnitOfWorkFactory
from .recovery import desktop_backup_status

_SAFE_REASON_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_ACTIVE_STATES = frozenset(
    {
        ComputeJobState.SUBMITTED,
        ComputeJobState.QUEUED,
        ComputeJobState.RUNNING,
    }
)
_MAX_REASON_CODE_SERIES = 32


class OperationalMetricsCollector(Protocol):
    def execute(self) -> dict[str, object]: ...


class CachedOperationalMetrics:
    """Bound repeated scrape cost while returning an isolated metrics snapshot."""

    def __init__(
        self,
        collector: OperationalMetricsCollector,
        *,
        ttl_seconds: float = 5.0,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("operational metrics cache TTL must be positive")
        self._collector = collector
        self._ttl_seconds = ttl_seconds
        self._lock = Lock()
        self._expires_at = 0.0
        self._snapshot: dict[str, object] | None = None

    def execute(self) -> dict[str, object]:
        now = monotonic()
        with self._lock:
            if self._snapshot is None or now >= self._expires_at:
                self._snapshot = deepcopy(self._collector.execute())
                self._expires_at = monotonic() + self._ttl_seconds
            return deepcopy(self._snapshot)


def _elapsed_microseconds(started_ns: int) -> int:
    return max(1, (monotonic_ns() - started_ns) // 1_000)


def _safe_failure_code(value: str) -> str:
    if _SAFE_REASON_CODE.fullmatch(value):
        return value
    return "UNSAFE_OR_UNKNOWN"


@dataclass(frozen=True, slots=True)
class ProductionOperationalMetrics:
    """Collect bounded metrics without returning identities, paths, or payloads."""

    profile: RuntimeProfile
    read_uow_factory: RuntimeUnitOfWorkFactory
    object_root: Path
    object_store: ObjectStore | None = None
    desktop_database: Path | None = None

    def _database_metrics(self) -> dict[str, object]:
        started_ns = monotonic_ns()
        with self.read_uow_factory() as uow:
            jobs = ComputeJobRepository(uow.canonical_rows).all()
            audits = uow.audit_log.rows()
            uow.commit()
        status_counts = {state.value: 0 for state in ComputeJobState}
        raw_failure_counts: dict[str, int] = {}
        for job in jobs:
            status_counts[job.status.value] += 1
            if job.status is not ComputeJobState.FAILED:
                continue
            codes = job.reason_codes or ("UNSPECIFIED_FAILURE",)
            for raw_code in codes:
                code = _safe_failure_code(raw_code)
                raw_failure_counts[code] = raw_failure_counts.get(code, 0) + 1

        ordered = sorted(
            raw_failure_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
        retained = ordered[:_MAX_REASON_CODE_SERIES]
        overflow = sum(count for _code, count in ordered[_MAX_REASON_CODE_SERIES:])
        failure_counts = dict(retained)
        if overflow:
            failure_counts["OTHER"] = overflow

        access_denial_count = sum(1 for item in audits if item.outcome == "DENY")
        adapter_error_count = sum(
            count for code, count in raw_failure_counts.items() if "ADAPTER" in code
        )
        return {
            "database_metric_query_latency_us": _elapsed_microseconds(started_ns),
            "job_status_counts": status_counts,
            "job_active_count": sum(status_counts[state.value] for state in _ACTIVE_STATES),
            "job_failure_code_counts": failure_counts,
            "adapter_error_count": adapter_error_count,
            "access_denial_count": access_denial_count,
        }

    def _object_metrics(self) -> dict[str, object]:
        started_ns = monotonic_ns()
        if self.object_store is not None:
            objects = self.object_store.inventory()
            return {
                "object_scan_latency_us": _elapsed_microseconds(started_ns),
                "object_count": len(objects),
                "object_bytes": sum(item.byte_size for item in objects),
                "storage_capacity_state": "BACKEND_MANAGED",
            }
        count = 0
        byte_size = 0
        for path in self.object_root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(self.object_root)
            if relative.parts[0] == ".locks" or path.name.endswith(".tmp"):
                continue
            try:
                size = path.stat().st_size
            except FileNotFoundError:
                continue
            count += 1
            byte_size += size
        capacity = shutil.disk_usage(self.object_root)
        return {
            "object_scan_latency_us": _elapsed_microseconds(started_ns),
            "object_count": count,
            "object_bytes": byte_size,
            "storage_capacity_bytes": capacity.total,
            "storage_used_bytes": capacity.used,
            "storage_free_bytes": capacity.free,
        }

    def _backup_metrics(self) -> dict[str, object]:
        if self.profile is RuntimeProfile.SERVICE:
            return {
                "schema": "TPAA_SERVICE_BACKUP_STATUS_V1",
                "profile": "SERVICE",
                "state": "EXTERNAL_GOVERNANCE_REQUIRED",
            }
        if self.desktop_database is None:
            raise RuntimeError("Desktop operational metrics require database")
        return desktop_backup_status(self.desktop_database)

    def execute(self) -> dict[str, object]:
        return {
            "operational_metrics_schema": "TPAA_OPERATIONAL_METRICS_V1",
            **self._database_metrics(),
            **self._object_metrics(),
            "backup_status": self._backup_metrics(),
        }


__all__ = ["CachedOperationalMetrics", "ProductionOperationalMetrics"]
