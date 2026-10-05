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


@dataclass(frozen=True, slots=True)
class ProductionRuntimeConfig:
    """PRCB production-only runtime configuration with explicit persistence."""

    profile: RuntimeProfile
    product_build_version: str
    authority_root: Path
    object_root: Path
    desktop_database_path: Path | None = None
    service_conninfo: str | None = None

    def __post_init__(self) -> None:
        if not self.product_build_version.strip():
            raise ValueError("product_build_version must be non-empty")
        if not self.authority_root.is_dir():
            raise ValueError("authority_root must exist")
        if self.profile is RuntimeProfile.DESKTOP:
            if self.desktop_database_path is None:
                raise ValueError("Desktop production runtime requires database_path")
            if not self.desktop_database_path.is_file():
                raise ValueError("Desktop production database_path must exist")
            if self.service_conninfo is not None:
                raise ValueError("Desktop production runtime forbids service_conninfo")
        else:
            if not self.service_conninfo or not self.service_conninfo.strip():
                raise ValueError("Service production runtime requires conninfo")
            if self.desktop_database_path is not None:
                raise ValueError("Service production runtime forbids desktop_database_path")
