"""Cross-platform runtime adapters admitted by the M0 platform boundary."""

from .filesystem import (
    PlatformFilesystem,
    PlatformPathError,
    casefold_name_key,
    ensure_no_case_collisions,
)
from .filesync import InterProcessFileLock, LockUnavailable, atomic_replace_bytes
from .worker import WorkerPayload, run_spawn_echo

__all__ = [
    "InterProcessFileLock",
    "LockUnavailable",
    "PlatformFilesystem",
    "PlatformPathError",
    "WorkerPayload",
    "atomic_replace_bytes",
    "casefold_name_key",
    "ensure_no_case_collisions",
    "run_spawn_echo",
]
