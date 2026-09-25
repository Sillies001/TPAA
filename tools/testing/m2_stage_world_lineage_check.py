#!/usr/bin/env python3
"""M2-WORLD-003 Basic Flight Stage/World lineage evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
M1_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "m1"
M2_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "m2"
STAGE = M1_FIXTURES / "BF_M1_NOMINAL_V1"
REFERENCE = M2_FIXTURES / "RT_M2_NOMINAL_V1"
TIME = M2_FIXTURES / "TA_M2_NOMINAL_V1"
MISSION = M2_FIXTURES / "MSI_M2_RADAR_V1"
ALIGNMENT = M2_FIXTURES / "MA_M2_NOMINAL_V1"
INSUFFICIENT = M2_FIXTURES / "MA_M2_INSUFFICIENT_V1"
RELEASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3"
ALTERNATE_RELEASE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb4"


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


def _project(alignment: Path, release_id: str):
    from tpaa_world import project_m2_stage_world_lineage

    return project_m2_stage_world_lineage(
        STAGE,
        REFERENCE,
        TIME,
        MISSION,
        alignment,
        authority_root=AUTHORITY_ROOT,
        release_id=release_id,
    )


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    world = _project(ALIGNMENT, RELEASE_ID)
    replayed = _project(ALIGNMENT, RELEASE_ID)
    alternate_release = _project(ALIGNMENT, ALTERNATE_RELEASE_ID)
    partial = _project(INSUFFICIENT, RELEASE_ID)

    summaries = {summary.world_role: summary for summary in world.summaries}
    partial_summaries = {summary.world_role: summary for summary in partial.summaries}
    acceptance = {
        "stage_profile_exact": world.stage_profile_id == "BASIC_FLIGHT_V1",
        "stage_order_exact": (
            tuple(stage.stage_type for stage in world.stage_projection.stages)
            == (
                "SETUP_ENTRY",
                "EXECUTION",
                "STABILIZATION_RECOVERY",
                "COMPLETION",
            )
        ),
        "stage_validity_exact": all(
            stage.stage_status == "VALID"
            for stage in world.stage_projection.stages
        ),
        "stage_coverage_exact": all(
            stage.coverage == 1.0 for stage in world.stage_projection.stages
        ),
        "stage_confidence_exact": all(
            stage.confidence == 1.0 for stage in world.stage_projection.stages
        ),
        "world_roles_exact": tuple(summaries) == (
            "REFERENCE_TRUTH_WORLD",
            "TIME_ALIGNMENT_WORLD",
            "RADAR_SENSOR_WORLD",
        ),
        "world_lineage_coverage_complete": (
            world.coverage == 1.0
            and all(summary.lineage_coverage == 1.0 for summary in world.summaries)
        ),
        "world_lineage_confidence_exact": (
            world.confidence == 1.0
            and all(summary.lineage_confidence == 1.0 for summary in world.summaries)
        ),
        "nominal_status_ready": (
            world.status == "READY"
            and all(summary.world_status == "READY" for summary in world.summaries)
        ),
        "partial_status_propagated": (
            partial.status == "PARTIAL"
            and partial_summaries["RADAR_SENSOR_WORLD"].world_status == "PARTIAL"
            and partial.coverage == 1.0
        ),
        "session_identity_exact": (
            world.session_id
            == world.reference_time_world.reference_manifest.session_id
            == world.reference_time_world.time_manifest.session_id
            == world.radar_sensor_world.manifest.session_id
        ),
        "world_manifests_not_rewritten": all(
            manifest.episode_id is None and manifest.stage_id is None
            for manifest in (
                world.reference_time_world.reference_manifest,
                world.reference_time_world.time_manifest,
                world.radar_sensor_world.manifest,
            )
        ),
        "stage_authority_not_rewritten": not world.stage_authority_rewritten,
        "world_manifest_not_rewritten": not world.world_manifest_rewritten,
        "replay_stable": world == replayed,
        "logical_content_release_independent": (
            world.logical_hash == alternate_release.logical_hash
            and tuple(summary.logical_hash for summary in world.summaries)
            == tuple(summary.logical_hash for summary in alternate_release.summaries)
        ),
        "world_identity_release_bound": (
            tuple(summary.world_product_id for summary in world.summaries)
            != tuple(
                summary.world_product_id
                for summary in alternate_release.summaries
            )
        ),
        "authority_hashes_bound": (
            len(world.stage_registry_sha256) == 64
            and len(world.core_schema_sha256) == 64
        ),
        "persistence_not_executed": not world.persistence_executed,
        "metric_logic_not_executed": not world.metric_logic_executed,
        "observation_projection_not_executed": (
            not world.observation_projection_executed
        ),
        "publication_not_executed": not world.release_publication_executed,
    }
    failed_acceptance = sorted(
        key for key, passed in acceptance.items() if not bool(passed)
    )
    logical_product = {
        "episode_id": world.episode_id,
        "session_id": world.session_id,
        "stage_profile_id": world.stage_profile_id,
        "stage_registry_sha256": world.stage_registry_sha256,
        "core_schema_sha256": world.core_schema_sha256,
        "status": world.status,
        "coverage": world.coverage,
        "confidence": world.confidence,
        "bundle_logical_hash": world.logical_hash,
        "stages": [
            {
                "stage_id": stage.stage_id,
                "stage_type": stage.stage_type,
                "stage_order": stage.stage_order,
                "start_session_time_us": stage.start_session_time_us,
                "end_session_time_us": stage.end_session_time_us,
                "stage_status": stage.stage_status,
                "coverage": stage.coverage,
                "confidence": stage.confidence,
                "detector_version": stage.detector_version,
            }
            for stage in world.stage_projection.stages
        ],
        "worlds": [
            {
                "world_role": summary.world_role,
                "world_version": summary.world_version,
                "world_status": summary.world_status,
                "world_logical_content_hash": summary.world_logical_content_hash,
                "lineage_coverage": summary.lineage_coverage,
                "lineage_confidence": summary.lineage_confidence,
                "stage_ids": summary.stage_ids,
                "stage_types": summary.stage_types,
                "logical_hash": summary.logical_hash,
            }
            for summary in world.summaries
        ],
        "records": [
            {
                "world_role": record.world_role,
                "world_version": record.world_version,
                "world_status": record.world_status,
                "world_logical_content_hash": record.world_logical_content_hash,
                "episode_id": record.episode_id,
                "stage_id": record.stage_id,
                "stage_type": record.stage_type,
                "stage_order": record.stage_order,
                "stage_status": record.stage_status,
                "stage_coverage": record.stage_coverage,
                "stage_confidence": record.stage_confidence,
                "detector_version": record.detector_version,
                "overlap_start_session_time_us": (
                    record.overlap_start_session_time_us
                ),
                "overlap_end_session_time_us": (
                    record.overlap_end_session_time_us
                ),
                "overlap_duration_us": record.overlap_duration_us,
            }
            for record in world.records
        ],
    }
    return {
        "schema": "TPAA_M2_WORLD_003_STAGE_WORLD_LINEAGE_EVIDENCE_V1",
        "task_id": "M2-WORLD-003",
        "tracking_issue": 96,
        "status": "PASS" if not failed_acceptance else "FAIL",
        "source_revision": _git_revision(),
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
            "schema": "TPAA_M2_WORLD_003_STAGE_WORLD_LINEAGE_EVIDENCE_V1",
            "task_id": "M2-WORLD-003",
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
