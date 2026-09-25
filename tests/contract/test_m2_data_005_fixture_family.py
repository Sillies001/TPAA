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


def test_m2_data_005_fixture_family_acceptance_and_expected_failures(tmp_path: Path) -> None:
    evidence_path = tmp_path / "fixture-family.json"
    result = _run(
        "m2-fixture-family-check",
        "--evidence",
        str(evidence_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M2_DATA_005_FIXTURE_FAMILY_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-DATA-005"
    assert evidence["status"] == "PASS"
    assert evidence["member_count"] == 9
    assert evidence["failed_acceptance"] == []
    assert evidence["required_categories"] == [
        "GAP",
        "INSUFFICIENT",
        "INVALID",
        "NOMINAL",
        "WRAP_BOUNDARY",
        "WRONG_SENSOR_APPLICABILITY",
    ]
    assert evidence["platform_policy"] == {
        "host_path_in_logical_product": False,
        "source_bytes": "REPOSITORY_CONTROLLED_IDENTICAL_BYTES",
        "windows_linux_constraint": "SAME_MANIFEST_AND_INPUT_SHA256",
    }

    members = {
        item["fixture_id"]: item for item in evidence["logical_product"]["members"]
    }
    assert members["TA_M2_INVALID_UNRESOLVED_V1"]["error_code"] == (
        "M2_TIME_ALIGNMENT_TIME_TRANSFORM_UNRESOLVED"
    )
    assert members["MSI_M2_IRST_NEGATIVE_V1"]["error_code"] == (
        "M2_MISSION_SYSTEM_NOT_APPLICABLE"
    )
    assert members["MA_M2_GAP_V1"]["status"] == "INSUFFICIENT"
    assert members["MA_M2_INSUFFICIENT_V1"]["status"] == "INSUFFICIENT"
    assert members["MA_M2_WRAP_BOUNDARY_V1"]["status"] == "READY"


def test_m2_data_005_cross_platform_compare_is_revision_exact(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    check = _run("m2-fixture-family-check", "--evidence", str(source))
    assert check.returncode == 0, check.stdout + check.stderr
    payload = json.loads(source.read_text(encoding="utf-8"))
    revision = payload["source_revision"]

    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"

    result = _run(
        "m2-fixture-family-compare",
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
    assert evidence["schema"] == "TPAA_M2_DATA_005_CROSS_PLATFORM_EVIDENCE_V1"
    assert evidence["status"] == "PASS"
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
