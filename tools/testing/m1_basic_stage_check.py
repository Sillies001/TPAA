"""Governed M1-WORLD-002 BASIC_FLIGHT_V1 Stage evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m1"
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
EXPECTED_ORDER = (
    "SETUP_ENTRY",
    "EXECUTION",
    "STABILIZATION_RECOVERY",
    "COMPLETION",
)


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

    from tpaa_episode import project_basic_flight_stages

    records: list[dict[str, object]] = []
    replay_stable = True
    expected_intervals_exact = True
    order_exact = True
    half_open_exact = True
    terminator_published_as_stage = False
    stable_stage_id_sets: set[tuple[str, ...]] = set()
    stage_count = 0
    for bundle in sorted(path for path in FIXTURE_ROOT.iterdir() if path.is_dir()):
        projection = project_basic_flight_stages(
            bundle,
            authority_root=AUTHORITY_ROOT,
        )
        replay = project_basic_flight_stages(
            bundle,
            authority_root=AUTHORITY_ROOT,
        )
        replay_stable = replay_stable and replay == projection
        expected = json.loads((bundle / "expected" / "expected.json").read_text(encoding="utf-8"))
        expected_stages = expected["stages"]
        projected_intervals = [
            (stage.stage_type, stage.start_session_time_us, stage.end_session_time_us)
            for stage in projection.stages
        ]
        expected_intervals = [
            (
                item["stage_type"],
                int(item["start_session_time_us"]),
                int(item["end_session_time_us"]),
            )
            for item in expected_stages
        ]
        expected_intervals_exact = (
            expected_intervals_exact and projected_intervals == expected_intervals
        )
        order_exact = (
            order_exact and tuple(stage.stage_type for stage in projection.stages) == EXPECTED_ORDER
        )
        half_open_exact = half_open_exact and all(
            left.end_session_time_us == right.start_session_time_us
            and not left.contains(left.end_session_time_us)
            and right.contains(right.start_session_time_us)
            for left, right in zip(projection.stages, projection.stages[1:], strict=False)
        )
        terminator_published_as_stage = terminator_published_as_stage or any(
            stage.stage_type == "END" for stage in projection.stages
        )
        stable_stage_id_sets.add(tuple(stage.stage_id for stage in projection.stages))
        stage_count += len(projection.stages)
        records.append(
            {
                "fixture_id": projection.fixture_id,
                "episode_id": projection.episode_id,
                "stage_profile_id": projection.stage_profile_id,
                "interval_semantics": projection.interval_semantics,
                "terminator_marker": projection.terminator_marker,
                "stages": [
                    {
                        "stage_id": stage.stage_id,
                        "stage_type": stage.stage_type,
                        "stage_order": stage.stage_order,
                        "start_session_time_us": stage.start_session_time_us,
                        "end_session_time_us": stage.end_session_time_us,
                        "precedence_source": stage.precedence_source,
                        "detection_method": stage.detection_method,
                    }
                    for stage in projection.stages
                ],
                "status": "PASS",
            }
        )

    status = (
        "PASS"
        if len(records) == 8
        and len(stable_stage_id_sets) == 1
        and replay_stable
        and expected_intervals_exact
        and order_exact
        and half_open_exact
        and not terminator_published_as_stage
        else "FAIL"
    )
    return {
        "schema": "TPAA_M1_WORLD_002_BASIC_STAGE_EVIDENCE_V1",
        "task_id": "M1-WORLD-002",
        "status": status,
        "source_revision": _git_revision(),
        "projector_version": "M1_BASIC_FLIGHT_STAGE_PROJECTOR_V1",
        "stage_profile_id": "BASIC_FLIGHT_V1",
        "precedence_source": "CONTEXT_OFFICIAL_MARKER",
        "detection_method": "CONTEXT",
        "ordered_stages": list(EXPECTED_ORDER),
        "interval_semantics": "half-open",
        "projection_count": len(records),
        "stage_count": stage_count,
        "unique_stage_id_set_count": len(stable_stage_id_sets),
        "replay_stable": replay_stable,
        "expected_intervals_exact": expected_intervals_exact,
        "order_exact": order_exact,
        "half_open_exact": half_open_exact,
        "terminator_marker": "END",
        "terminator_published_as_stage": terminator_published_as_stage,
        "database_persistence_executed": False,
        "stage_quality_projection_executed": False,
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
            "schema": "TPAA_M1_WORLD_002_BASIC_STAGE_EVIDENCE_V1",
            "task_id": "M1-WORLD-002",
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
