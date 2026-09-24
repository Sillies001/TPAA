from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"
POLICY = REPO_ROOT / "tools" / "testing" / "M1_FIXTURE_POLICY.json"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_m1_fixture_policy_has_exact_eight_bundle_ids() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    ids = {item["id"] for item in policy["bundles"]}

    assert ids == {
        "BF_M1_NOMINAL_V1",
        "BF_M1_GAP_V1",
        "BF_M1_ANGLE_WRAP_V1",
        "BF_M1_STRUCTURED_PARTIAL_V1",
        "BF_M1_STAGE_BOUNDARY_V1",
        "BF_M1_REPLAY_V1",
        "BF_M1_CROSS_PLATFORM_V1",
        "BF_M1_FAILURE_V1",
    }
    assert policy["data_governance"]["default_allowed_classifications"] == ["SYNTHETIC"]


def test_m1_fixture_check_is_available_through_unified_cli(tmp_path: Path) -> None:
    evidence_path = tmp_path / "m1-fixtures.json"
    result = _run(
        str(DEV),
        "m1-fixture-check",
        "--evidence",
        str(evidence_path),
    )

    assert result.returncode == 0, result.stderr
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["status"] == "PASS"
    assert evidence["task_id"] == "M1-TST-001"
    assert evidence["bundle_count"] == 8


def test_single_bundle_validation_preserves_task_boundary() -> None:
    result = _run(
        str(DEV),
        "m1-fixture-check",
        "--bundle",
        "BF_M1_NOMINAL_V1",
    )

    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"
    assert evidence["bundle_count"] == 1
    assert evidence["bundles"][0]["fixture_id"] == "BF_M1_NOMINAL_V1"
