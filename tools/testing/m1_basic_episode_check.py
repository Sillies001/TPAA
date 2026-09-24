"""Governed M1-WORLD-001 Basic Episode acceptance evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m1"
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"


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

    from tpaa_episode import detect_basic_episode

    records: list[dict[str, object]] = []
    replay_stable = True
    expected_intervals_exact = True
    for bundle in sorted(path for path in FIXTURE_ROOT.iterdir() if path.is_dir()):
        episode = detect_basic_episode(
            bundle,
            authority_root=AUTHORITY_ROOT,
        )
        replay = detect_basic_episode(
            bundle,
            authority_root=AUTHORITY_ROOT,
        )
        replay_stable = replay_stable and replay == episode
        expected = json.loads((bundle / "expected" / "expected.json").read_text(encoding="utf-8"))
        expected_episode = expected["episode"]
        expected_intervals_exact = expected_intervals_exact and (
            episode.start_session_time_us == int(expected_episode["start_session_time_us"])
            and episode.end_session_time_us == int(expected_episode["end_session_time_us"])
            and episode.episode_type == expected_episode["episode_type"]
        )
        records.append(
            {
                "fixture_id": episode.fixture_id,
                "episode_id": episode.episode_id,
                "session_id": episode.session_id,
                "context_id": episode.context_id,
                "primary_aircraft_id": episode.primary_aircraft_id,
                "start_session_time_us": episode.start_session_time_us,
                "end_session_time_us": episode.end_session_time_us,
                "revision_no": episode.revision_no,
                "logical_hash": episode.logical_hash,
                "status": "PASS",
            }
        )

    unique_ids = {record["episode_id"] for record in records}
    unique_hashes = {record["logical_hash"] for record in records}
    same_governed_identity_across_fixtures = (
        len(unique_ids) == 1 and len(unique_hashes) == 1
    )
    status = (
        "PASS"
        if len(records) == 8
        and same_governed_identity_across_fixtures
        and replay_stable
        and expected_intervals_exact
        else "FAIL"
    )
    return {
        "schema": "TPAA_M1_WORLD_001_BASIC_EPISODE_EVIDENCE_V1",
        "task_id": "M1-WORLD-001",
        "status": status,
        "source_revision": _git_revision(),
        "detector_version": "M1_BASIC_FLIGHT_EPISODE_V1",
        "episode_type": "BASIC_FLIGHT",
        "subject_scope": "AIRCRAFT",
        "projection_count": len(records),
        "unique_episode_id_count": len(unique_ids),
        "unique_logical_hash_count": len(unique_hashes),
        "same_governed_identity_across_fixtures": (
            same_governed_identity_across_fixtures
        ),
        "replay_stable": replay_stable,
        "expected_intervals_exact": expected_intervals_exact,
        "revision_no": 1,
        "supersedes_episode_id": None,
        "database_persistence_executed": False,
        "stage_projection_executed": False,
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
            "schema": "TPAA_M1_WORLD_001_BASIC_EPISODE_EVIDENCE_V1",
            "task_id": "M1-WORLD-001",
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
