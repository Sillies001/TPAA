#!/usr/bin/env python3
"""M2-WORLD-002 RADAR sensor World product evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m2"
MISSION = FIXTURE_ROOT / "MSI_M2_RADAR_V1"
NON_RADAR = FIXTURE_ROOT / "MSI_M2_IRST_NEGATIVE_V1"
ALIGNMENT = FIXTURE_ROOT / "MA_M2_NOMINAL_V1"
INSUFFICIENT = FIXTURE_ROOT / "MA_M2_INSUFFICIENT_V1"
RELEASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2"
ALTERNATE_RELEASE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb3"


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    value = completed.stdout.strip()
    return value if len(value) == 40 else "UNKNOWN"


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_ingest import M2MissionSystemError
    from tpaa_world import (
        CORE_WORLD_MANIFEST_WRITABLE_FIELDS,
        CoreWorldManifest,
        project_m2_radar_sensor_world,
    )

    world = project_m2_radar_sensor_world(
        MISSION,
        ALIGNMENT,
        authority_root=AUTHORITY_ROOT,
        release_id=RELEASE_ID,
    )
    replayed = project_m2_radar_sensor_world(
        MISSION,
        ALIGNMENT,
        authority_root=AUTHORITY_ROOT,
        release_id=RELEASE_ID,
    )
    alternate_release = project_m2_radar_sensor_world(
        MISSION,
        ALIGNMENT,
        authority_root=AUTHORITY_ROOT,
        release_id=ALTERNATE_RELEASE_ID,
    )
    insufficient = project_m2_radar_sensor_world(
        MISSION,
        INSUFFICIENT,
        authority_root=AUTHORITY_ROOT,
        release_id=RELEASE_ID,
    )
    non_radar_fail_closed = False
    non_radar_error_code: str | None = None
    try:
        project_m2_radar_sensor_world(
            NON_RADAR,
            ALIGNMENT,
            authority_root=AUTHORITY_ROOT,
            release_id=RELEASE_ID,
        )
    except M2MissionSystemError as exc:
        non_radar_error_code = exc.code
        non_radar_fail_closed = exc.code == "M2_MISSION_SYSTEM_NOT_APPLICABLE"

    manifest_fields = tuple(item.name for item in fields(CoreWorldManifest))
    acceptance = {
        "core_manifest_contract_exact": (
            manifest_fields == CORE_WORLD_MANIFEST_WRITABLE_FIELDS
        ),
        "world_kind_machine": world.manifest.world_kind == "MACHINE",
        "world_status_ready": world.manifest.status == "READY",
        "subject_type_exact": world.subject_type == "MISSION_SYSTEM_INSTANCE",
        "subject_identity_preserved": (
            world.mission_system_instance_id
            == world.mission_system.instance.mission_system_instance_id
            == world.measurement_alignment.mission_system_instance_id
        ),
        "aircraft_identity_preserved": (
            world.manifest.aircraft_id
            == world.mission_system.instance.aircraft_id
        ),
        "core_entity_subject_not_fabricated": world.manifest.subject_id is None,
        "radar_applicability_exact": (
            world.applicability_mode == "SYSTEM_TYPE_EXACT"
            and world.allowed_system_types == ("RADAR",)
            and world.mission_system.instance.system_type == "RADAR"
            and world.mission_system.sns_applicable
        ),
        "non_radar_fails_closed": non_radar_fail_closed,
        "measurement_alignment_preserved": (
            world.measurement_alignment.mission_system_logical_hash
            == world.mission_system.logical_hash
            and world.measurement_alignment.coverage == world.manifest.coverage
        ),
        "insufficient_maps_to_partial": (
            insufficient.measurement_alignment.status == "INSUFFICIENT"
            and insufficient.manifest.status == "PARTIAL"
            and bool(insufficient.manifest.reason_codes)
        ),
        "replay_stable": world == replayed,
        "logical_content_release_independent": (
            world.logical_hash == alternate_release.logical_hash
            and world.manifest.logical_content_hash
            == alternate_release.manifest.logical_content_hash
        ),
        "world_identity_release_bound": (
            world.manifest.world_product_id
            != alternate_release.manifest.world_product_id
            and world.manifest.request_hash
            != alternate_release.manifest.request_hash
        ),
        "authority_hashes_bound": all(
            len(value) == 64
            for value in (
                world.core_schema_sha256,
                world.world_policy_sha256,
                world.metric_catalog_sha256,
                world.metric_input_authority_sha256,
            )
        ),
        "no_shadow_schema": not world.shadow_schema_created,
        "metric_logic_not_executed": not world.metric_logic_executed,
        "stage_projection_not_executed": not world.stage_projection_executed,
        "persistence_not_executed": not world.persistence_executed,
        "observation_projection_not_executed": (
            not world.observation_projection_executed
        ),
        "publication_not_executed": not world.release_publication_executed,
        "detection_contracts_not_fabricated": (
            not world.detection_opportunity_rebuilt
            and not world.detection_confirmation_rebuilt
        ),
    }
    failed_acceptance = sorted(
        key for key, passed in acceptance.items() if not bool(passed)
    )
    logical_product = {
        "session_id": world.manifest.session_id,
        "world_kind": world.manifest.world_kind,
        "world_version": world.manifest.world_version,
        "world_status": world.manifest.status,
        "coverage": world.manifest.coverage,
        "reason_codes": world.manifest.reason_codes,
        "logical_content_hash": world.manifest.logical_content_hash,
        "source_authority_signature": world.manifest.source_authority_signature,
        "bundle_logical_hash": world.logical_hash,
        "subject": {
            "subject_type": world.subject_type,
            "mission_system_instance_id": world.mission_system_instance_id,
            "identity_ref": world.mission_system.identity.identity_ref,
            "source_entity_key": world.mission_system.identity.source_entity_key,
            "aircraft_id": world.mission_system.instance.aircraft_id,
            "system_type": world.mission_system.instance.system_type,
            "system_code": world.mission_system.instance.system_code,
            "configuration_hash": world.mission_system.instance.configuration_hash,
        },
        "applicability": {
            "mode": world.applicability_mode,
            "allowed_system_types": world.allowed_system_types,
        },
        "alignment": {
            "fixture_id": world.measurement_alignment.fixture_id,
            "target_pair_id": world.measurement_alignment.target_pair_id,
            "logical_hash": world.measurement_alignment.logical_hash,
            "quality_profile_hash": (
                world.measurement_alignment.quality_profile.profile_hash
            ),
            "row_count": len(world.measurement_alignment.rows),
        },
        "authority": {
            "core_schema_sha256": world.core_schema_sha256,
            "world_policy_sha256": world.world_policy_sha256,
            "metric_catalog_sha256": world.metric_catalog_sha256,
            "metric_input_authority_sha256": (
                world.metric_input_authority_sha256
            ),
        },
    }
    return {
        "schema": "TPAA_M2_WORLD_002_RADAR_SENSOR_EVIDENCE_V1",
        "task_id": "M2-WORLD-002",
        "tracking_issue": 96,
        "status": "PASS" if not failed_acceptance else "FAIL",
        "source_revision": _git_revision(),
        "mission_fixture_id": world.mission_system.fixture_id,
        "alignment_fixture_id": world.measurement_alignment.fixture_id,
        "non_radar_error_code": non_radar_error_code,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed_acceptance,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    try:
        payload = verify()
        return_code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M2_WORLD_002_RADAR_SENSOR_EVIDENCE_V1",
            "task_id": "M2-WORLD-002",
            "tracking_issue": 96,
            "status": "FAIL",
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2

    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
