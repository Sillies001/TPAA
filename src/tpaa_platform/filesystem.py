"""OS-neutral path handling above the TPAA platform adapter boundary."""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

_OBJECT_ROOT_ENV: Final = "TPAA_OBJECT_ROOT"


class PlatformPathError(ValueError):
    """A logical path cannot be mapped safely on the current platform."""


def casefold_name_key(name: str) -> str:
    """Return the governed Unicode/case collision key."""

    if not name:
        raise PlatformPathError("path segment must not be empty")
    return unicodedata.normalize("NFC", name).casefold()


def ensure_no_case_collisions(names: list[str] | tuple[str, ...]) -> None:
    """Reject names that are distinct text but collide on case-insensitive filesystems."""

    seen: dict[str, str] = {}
    for name in names:
        key = casefold_name_key(name)
        previous = seen.get(key)
        if previous is not None and previous != name:
            raise PlatformPathError(
                f"case/unicode collision: {previous!r} conflicts with {name!r}"
            )
        seen[key] = name


def _logical_segments(relative: str) -> tuple[str, ...]:
    if "\\" in relative:
        raise PlatformPathError("logical paths use '/' separators only")
    logical = PurePosixPath(relative)
    if logical.is_absolute():
        raise PlatformPathError("logical path must be relative")
    parts = logical.parts
    if not parts:
        raise PlatformPathError("logical path must not be empty")
    if any(part in {"", ".", ".."} for part in parts):
        raise PlatformPathError("logical path contains unsafe segment")
    if any(":" in part for part in parts):
        raise PlatformPathError("logical path segment must not contain ':'")
    return tuple(unicodedata.normalize("NFC", part) for part in parts)


def default_user_data_root() -> Path:
    """Return the M0 user-data root without hard-coded drive or /tmp assumptions."""

    override = os.environ.get(_OBJECT_ROOT_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".tpaa").resolve()


@dataclass(frozen=True)
class PlatformFilesystem:
    """Resolve governed POSIX-style logical paths below one physical root."""

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.expanduser().resolve())

    def resolve(self, relative: str) -> Path:
        current = self.root
        for segment in _logical_segments(relative):
            current = current / segment
        resolved = current.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise PlatformPathError("resolved path escapes platform root")
        return resolved

    def ensure_root(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root
