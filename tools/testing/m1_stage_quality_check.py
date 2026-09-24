"""Governed M1-WORLD-003 Stage quality/status evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m1"
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
EXPECTED_DETECTOR_VERSION = "M1_BASIC_FLIGHT_STAGE_PROJECTOR_V1"


def _git_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    return value if len(value) == 40 else "UNKNOWN"


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_episode import (
        project_basic_flight_stage_quality,
        project_basic_flight_stages,
    )

    records: list[dict[str, object]] = []
    stage_count = 0
    replay_stable = True
    world_002_projection_preserved = True
    quality_fields_exact = True
    numeric_bounds_valid = True
    stable_stage_id_sets: set[tuple[str, ...]] = set()

    for bundle in sorted(path for path in FIXTURE_ROOT.iterdir() if path.is_dir()):
        base = project_basic_flight_stages(bundle, authority_root=AUTHORITY_ROOT)
        projection = project_basic_flight_stage_quality(bundle, authority_root=AUTHORITY_ROOT)
        replay = project_basic_flight_stage_quality(bundle, authority_root=AUTHORITY_ROOT)
        replay_stable = replay_stable and replay == projection
        stable_stage_id_sets.add(tuple(stage.stage_id for stage in projection.stages))
        stage_count += len(projection.stages)

        for source, qualified in zip(base.stages, projection.stages, strict=True):
            world_002_projection_preserved = world_002_projection_preserved and (
                qualified.episode_id,
                qualified.stage_id,
                qualified.stage_profile_id,
                qualified.stage_type,
                qualified.stage_order,
                qualified.start_session_time_us,
                qualified.end_session_time_us,
                qualified.precedence_source,
                qualified.detection_method,
            ) == (
                source.episode_id,
                source.stage_id,
                source.stage_profile_id,
                source.stage_type,
                source.stage_order,
                source.start_session_time_us,
                source.end_session_time_us,
                source.precedence_source,
                source.detection_method,
            )
            quality_fields_exact = quality_fields_exact and (
                qualified.stage_status == "VALID"
                and qualified.coverage == 1.0
                and qualified.confidence == 1.0
                and qualified.detector_version == EXPECTED_DETECTOR_VERSION
            )
            numeric_bounds_valid = numeric_bounds_valid and (
                0.0 <= qualified.coverage <= 1.0 and 0.0 <= qualified.confidence <= 1.0
            )

        records.append(
            {
                "fixture_id": projection.fixture_id,
                "episode_id": projection.episode_id,
                "stages": [
                    {
                        "stage_id": stage.stage_id,
                        "stage_type": stage.stage_type,
                        "stage_order": stage.stage_order,
                        "stage_status": stage.stage_status,
                        "coverage": stage.coverage,
                        "confidence": stage.confidence,
                        "detector_version": stage.detector_version,
                    }
                    for stage in projection.stages
                ],
                "status": "PASS",
            }
        )

    status = (
        "PASS"
        if len(records) == 8
        and stage_count == 32
        and len(stable_stage_id_sets) == 1
        and replay_stable
        and world_002_projection_preserved
        and quality_fields_exact
        and numeric_bounds_valid
        else "FAIL"
    )
    return {
        "schema": "TPAA_M1_WORLD_003_STAGE_QUALITY_EVIDENCE_V1",
        "task_id": "M1-WORLD-003",
        "status": status,
        "source_revision": _git_revision(),
        "stage_status": "VALID",
        "coverage": 1.0,
        "confidence": 1.0,
        "detector_version": EXPECTED_DETECTOR_VERSION,
        "quality_basis": "COMPLETE_AUTHORITATIVE_OFFICIAL_MARKERS",
        "projection_count": len(records),
        "stage_count": stage_count,
        "unique_stage_id_set_count": len(stable_stage_id_sets),
        "replay_stable": replay_stable,
        "world_002_projection_preserved": world_002_projection_preserved,
        "quality_fields_exact": quality_fields_exact,
        "numeric_bounds_valid": numeric_bounds_valid,
        "database_persistence_executed": False,
        "stage_quality_projection_executed": True,
        "revision_supersede_executed": False,
        "logical_hash_executed": False,
        "evidence_refs_projected": False,
        "world_projection_executed": False,
        "metric_logic_executed": False,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        payload = verify()
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M1_WORLD_003_STAGE_QUALITY_EVIDENCE_V1",
            "task_id": "M1-WORLD-003",
            "status": "FAIL",
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
