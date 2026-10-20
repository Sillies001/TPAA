"""Shared consistency-point paths for Desktop writes and recovery."""

from __future__ import annotations

from pathlib import Path


def desktop_write_quiescence_lock(object_root: Path) -> Path:
    """Return the single cross-process lock governing Desktop write snapshots."""

    return object_root / ".locks" / "runtime-write-quiescence.lock"


__all__ = ["desktop_write_quiescence_lock"]
