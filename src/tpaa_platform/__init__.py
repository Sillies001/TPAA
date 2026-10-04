"""Cross-platform runtime adapters admitted by the M0 platform boundary."""

from .filesync import InterProcessFileLock, LockUnavailable, atomic_replace_bytes
from .filesystem import (
    PlatformFilesystem,
    PlatformPathError,
    casefold_name_key,
    ensure_no_case_collisions,
)
from .polars_runtime import (
    EXPECTED_POLARS_VERSION,
    GovernedPolarsRuntime,
    PolarsRuntimeError,
    PolarsRuntimeIdentity,
)
from .worker import (
    SpawnWorkerDispatcher,
    WorkerAdmissionController,
    WorkerBackpressureError,
    WorkerCancelledError,
    WorkerClosedError,
    WorkerDispatchError,
    WorkerPayload,
    WorkerResult,
    WorkerTimeoutError,
    run_spawn_echo,
)

__all__ = [
    "EXPECTED_POLARS_VERSION",
    "GovernedPolarsRuntime",
    "PolarsRuntimeError",
    "PolarsRuntimeIdentity",
    "InterProcessFileLock",
    "LockUnavailable",
    "PlatformFilesystem",
    "PlatformPathError",
    "SpawnWorkerDispatcher",
    "WorkerAdmissionController",
    "WorkerBackpressureError",
    "WorkerCancelledError",
    "WorkerClosedError",
    "WorkerDispatchError",
    "WorkerResult",
    "WorkerTimeoutError",
    "WorkerPayload",
    "atomic_replace_bytes",
    "casefold_name_key",
    "ensure_no_case_collisions",
    "run_spawn_echo",
]
