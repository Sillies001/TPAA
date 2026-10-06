#!/usr/bin/env python3
"""PRCB C5 installed production runtime entry for TPAA 1.0.1 candidates."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = APP_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_runtime import (  # noqa: E402
    ProductionRuntime,
    ProductionRuntimeConfig,
    RuntimeProfile,
    build_desktop_production_runtime,
    build_service_production_runtime,
)

PRODUCT_VERSION = "1.0.1"
DESKTOP_PROFILES = {"WINDOWS_DESKTOP_X64", "LINUX_DESKTOP_X64"}
SERVICE_PROFILES = {"WINDOWS_SERVICE_X64", "LINUX_SERVICE_X64"}
ALL_PROFILES = DESKTOP_PROFILES | SERVICE_PROFILES


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _authority_root() -> Path:
    root = APP_ROOT / "baseline" / "CB-1.4.0" / "canonical"
    if not root.is_dir():
        raise RuntimeError("packaged canonical authority is unavailable")
    return root


def _runtime(profile_id: str) -> ProductionRuntime:
    object_root = Path(_required_env("TPAA_OBJECT_ROOT"))
    if profile_id in DESKTOP_PROFILES:
        database = Path(_required_env("TPAA_DESKTOP_DATABASE"))
        config = ProductionRuntimeConfig(
            profile=RuntimeProfile.DESKTOP,
            product_build_version=PRODUCT_VERSION,
            authority_root=_authority_root(),
            object_root=object_root,
            desktop_database_path=database,
        )
        return build_desktop_production_runtime(config)
    if profile_id in SERVICE_PROFILES:
        config = ProductionRuntimeConfig(
            profile=RuntimeProfile.SERVICE,
            product_build_version=PRODUCT_VERSION,
            authority_root=_authority_root(),
            object_root=object_root,
            service_conninfo=_required_env("TPAA_SERVICE_CONNINFO"),
        )
        return build_service_production_runtime(config)
    raise ValueError(f"unsupported PRCB runtime profile: {profile_id}")


def _ready(profile_id: str) -> dict[str, object]:
    runtime = _runtime(profile_id)
    availability = runtime.feature_availability.execute()
    return {
        "schema": "TPAA_PRCB_C5_INSTALLED_RUNTIME_READY_V1",
        "status": "PASS",
        "profile_id": profile_id,
        "runtime_profile": runtime.config.profile.value,
        "product_version": runtime.config.product_build_version,
        "db_schema_version": "1.9.0",
        "canonical_baseline": "CB-1.4.0",
        "feature_availability": availability,
        "production_composition": True,
        "tests_fixture_dependency": False,
        "formal_release_claimed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=sorted(ALL_PROFILES))
    parser.add_argument("command", choices=("ready",))
    args = parser.parse_args()
    print(json.dumps(_ready(args.profile), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
