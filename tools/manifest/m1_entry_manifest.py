#!/usr/bin/env python3
"""Generate the SDIB-1.0.1 M1 Entry build manifest for the current revision.

This is transition evidence only. Generating the manifest does not admit M1 and
does not qualify any M1 capability.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.manifest.build_artifacts import VALID_PROFILES, build_evidence

SCHEMA = "TPAA_M1_ENTRY_BUILD_MANIFEST_V1"
HISTORICAL_M0_TAG = "M0_IMPLEMENTATION_BASELINE"
HISTORICAL_M0_TARGET = "ee54e8500381e62a53e1f2352d485ed11892c9d6"


def build_manifest(profile: str) -> dict[str, object]:
    base = build_evidence(profile)["build-manifest.json"]
    canonical_obj = base.get("canonical_artifact_hashes")
    if not isinstance(canonical_obj, dict):
        raise RuntimeError("canonical artifact hash map unavailable")
    canonical_hashes: dict[str, str] = {}
    for key, value in canonical_obj.items():
        if isinstance(key, str) and isinstance(value, str):
            canonical_hashes[key] = value

    def required_hash(name: str) -> str:
        value = canonical_hashes.get(name)
        if not isinstance(value, str) or len(value) != 64:
            raise RuntimeError(f"required authority hash unavailable: {name}")
        return value

    source_revision = base.get("source_revision")
    core_baseline = base.get("core_baseline")
    db_schema_version = base.get("db_schema_version")
    baseline_lock_sha256 = base.get("baseline_lock_sha256")
    dependency_lock_sha256 = base.get("dependency_lock_sha256")
    platform_profile = base.get("platform_profile")
    for field_name, value in (
        ("source_revision", source_revision),
        ("core_baseline", core_baseline),
        ("db_schema_version", db_schema_version),
        ("baseline_lock_sha256", baseline_lock_sha256),
        ("dependency_lock_sha256", dependency_lock_sha256),
        ("platform_profile", platform_profile),
    ):
        if not isinstance(value, str) or not value:
            raise RuntimeError(f"required build field unavailable: {field_name}")

    return {
        "schema": SCHEMA,
        "status": "FROZEN_ENTRY_CANDIDATE",
        "admission": "M1_NOT_ADMITTED_BY_THIS_MANIFEST",
        "sdib": "SDIB-1.0.1",
        "source_revision": source_revision,
        "core_baseline": core_baseline,
        "db_schema_version": db_schema_version,
        "baseline_lock_sha256": baseline_lock_sha256,
        "dependency_lock_sha256": dependency_lock_sha256,
        "p1_metric_catalog_sha256": required_hash("P1_METRIC_CATALOG.json"),
        "stage_authority_sha256": required_hash("STAGE_REGISTRY.json"),
        "dto_authority_sha256": required_hash("CROSS_LAYER_DTO_CONTRACTS.json"),
        "platform_profile": platform_profile,
        "historical_m0_baseline": {
            "tag": HISTORICAL_M0_TAG,
            "target_revision": HISTORICAL_M0_TARGET,
        },
    }


def write_manifest(profile: str, output: Path) -> dict[str, object]:
    payload = build_manifest(profile)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=sorted(VALID_PROFILES))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = write_manifest(args.profile, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
