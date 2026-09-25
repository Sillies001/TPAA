from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_world_003_stage_authority_remains_frozen() -> None:
    stage = json.loads(
        (AUTHORITY / "STAGE_REGISTRY.json").read_text(encoding="utf-8")
    )
    core = json.loads(
        (AUTHORITY / "CORE_LOGICAL_MODEL.json").read_text(encoding="utf-8")
    )

    assert stage["registry_id"] == "STAGE_REGISTRY"
    assert stage["version"] == "1.1.0"
    assert stage["governance"]["time_interval"] == (
        "half-open [start_session_time_us,end_session_time_us)"
    )
    assert stage["profiles"]["BASIC_FLIGHT_V1"]["ordered_stages"] == [
        "SETUP_ENTRY",
        "EXECUTION",
        "STABILIZATION_RECOVERY",
        "COMPLETION",
    ]
    assert core["db_schema_version"] == "1.6.0"
    fields = [
        item["name"]
        for item in core["tables"]["episode.episode_stage"]["fields"]
    ]
    assert fields == [
        "stage_id",
        "episode_id",
        "stage_type",
        "stage_order",
        "start_session_time_us",
        "end_session_time_us",
        "detection_method",
        "stage_status",
        "coverage",
        "confidence",
        "detector_version",
        "supersedes_stage_id",
        "created_at",
    ]


def test_world_003_evidence_is_complete_and_status_preserving(tmp_path: Path) -> None:
    evidence_path = tmp_path / "world.json"
    result = _run(
        "m2-stage-world-lineage-check",
        "--evidence",
        str(evidence_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M2_WORLD_003_STAGE_WORLD_LINEAGE_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-WORLD-003"
    assert evidence["tracking_issue"] == 96
    assert evidence["status"] == "PASS"
    assert evidence["failed_acceptance"] == []
    assert all(evidence["acceptance"].values())

    product = evidence["logical_product"]
    assert product["stage_profile_id"] == "BASIC_FLIGHT_V1"
    assert product["status"] == "READY"
    assert product["coverage"] == 1.0
    assert product["confidence"] == 1.0
    assert [stage["stage_type"] for stage in product["stages"]] == [
        "SETUP_ENTRY",
        "EXECUTION",
        "STABILIZATION_RECOVERY",
        "COMPLETION",
    ]
    assert [world["world_role"] for world in product["worlds"]] == [
        "REFERENCE_TRUTH_WORLD",
        "TIME_ALIGNMENT_WORLD",
        "RADAR_SENSOR_WORLD",
    ]
    assert all(world["lineage_coverage"] == 1.0 for world in product["worlds"])
    assert len(product["bundle_logical_hash"]) == 64


def test_world_003_cross_platform_compare_is_revision_exact(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    checked = _run(
        "m2-stage-world-lineage-check",
        "--evidence",
        str(source),
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    payload = json.loads(source.read_text(encoding="utf-8"))
    revision = payload["source_revision"]

    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"

    result = _run(
        "m2-stage-world-lineage-compare",
        "--windows",
        str(windows),
        "--linux",
        str(linux),
        "--expected-revision",
        revision,
        "--evidence",
        str(compared),
    )
    assert result.returncode == 0, result.stdout + result.stderr

    evidence = json.loads(compared.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M2_WORLD_003_CROSS_PLATFORM_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-WORLD-003"
    assert evidence["status"] == "PASS"
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
