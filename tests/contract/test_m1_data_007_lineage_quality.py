from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_m1_data_007_acceptance_command_emits_machine_evidence(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "lineage-quality.json"
    result = _run(
        "m1-lineage-quality-check",
        "--evidence",
        str(evidence_path),
    )
    assert result.returncode == 0, result.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M1_DATA_007_LINEAGE_QUALITY_EVIDENCE_V1"
    assert evidence["task_id"] == "M1-DATA-007"
    assert evidence["status"] == "PASS"
    assert evidence["projection_count"] == 8
    assert evidence["total_row_count"] == 62
    assert evidence["field_lineage_count"] == 434
    assert evidence["traceable_field_count"] == 434
    assert evidence["missing_value_count"] == 8
    assert evidence["missing_preserved_as_null"] is True
    assert evidence["invalid_source_values_fail_closed"] is True
    assert evidence["zero_fill_of_missing_or_invalid_executed"] is False
    assert evidence["quality_mask_propagation_exact"] is True
    assert evidence["immutable_source_refs_verified"] is True
    assert evidence["replay_stable"] is True
    assert evidence["unique_logical_hash_count"] == 8
    assert evidence["database_persistence_executed"] is False
    assert evidence["episode_projection_executed"] is False
    assert evidence["stage_projection_executed"] is False
    assert evidence["world_projection_executed"] is False
    assert evidence["metric_logic_executed"] is False


def test_m1_data_007_every_record_binds_source_hash_into_ref() -> None:
    result = _run("m1-lineage-quality-check")
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)

    for record in evidence["records"]:
        assert record["source_artifact_sha256"] in record["source_artifact_ref"]
        assert record["field_lineage_count"] == record["row_count"] * 7
