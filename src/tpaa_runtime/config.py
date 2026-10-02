"""PIQB B1 product runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class RuntimeProfile(StrEnum):
    """Supported product runtime profiles."""

    DESKTOP = "DESKTOP"
    SERVICE = "SERVICE"


@dataclass(frozen=True, slots=True)
class ProductRuntimeConfig:
    """Engine-neutral composition inputs for one TPAA product runtime."""

    profile: RuntimeProfile
    product_build_version: str
    authority_root: Path
    m1_fixture_root: Path | None = None

    def __post_init__(self) -> None:
        if not self.product_build_version.strip():
            raise ValueError("product_build_version must be non-empty")
        if not self.authority_root.is_dir():
            raise ValueError("authority_root must exist")
        if self.m1_fixture_root is not None and not self.m1_fixture_root.is_dir():
            raise ValueError("m1_fixture_root must exist when configured")
