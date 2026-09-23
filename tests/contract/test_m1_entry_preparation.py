from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"
VERIFY_MODULE = "tools.governance.verify_m1_entry_preparation"
BACKLOG = REPO_ROOT / "docs" / "planning" / "M1_BACKLOG_IMPORT.json"
FIXTURE_POLICY = REPO_ROOT / "tools" / "testing" / "M1_FIXTURE_POLICY.json"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _profile() -> str:
    return "WINDOWS_DESKTOP_X64" if sys.platform == "win32" else "LINUX_DESKTOP_X64"


def test_m1_entry_preparation_verifier_passes_without_admitting_m1() -> None:
    result = _run("-m", VERIFY_MODULE)
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["schema"] == "TPAA_M1_ENTRY_PREPARATION_VERIFICATION_V1"
    assert evidence["status"] == "PASS"
    assert evidence["admission"] == "M1_NOT_ADMITTED"
    assert evidence["condition_8"] == "NOT_EVALUATED_HUMAN_ASSIGNMENT_REQUIRED"
    assert all(item["status"] == "PASS" for item in evidence["checks"])


def test_backlog_import_contains_exactly_56_unique_m1_task_ids() -> None:
    payload = json.loads(BACKLOG.read_text(encoding="utf-8"))
    records = payload["records"]
    task_ids = [item["task_id"] for item in records]
    issue_urls = [item["issue"]["url"] for item in records]
    assert payload["task_count"] == 56
    assert payload["imported_issue_count"] == 56
    assert len(records) == 56
    assert len(set(task_ids)) == 56
    assert len(issue_urls) == 56
    assert all(url.startswith("https://github.com/Sillies001/TPAA/issues/") for url in issue_urls)
    assert payload["admission_boundary"] == "PLANNING_ONLY_M1_NOT_ADMITTED"


def test_fixture_policy_is_synthetic_and_has_exact_eight_bundles() -> None:
    payload = json.loads(FIXTURE_POLICY.read_text(encoding="utf-8"))
    ids = {item["id"] for item in payload["bundles"]}
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
    data = payload["data_governance"]
    assert data["default_allowed_classifications"] == ["SYNTHETIC"]
    assert data["operational_dependency"] is False
    assert data["sensitive_dependency"] is False
    assert payload["expected_result_independence"]["golden_reviewer_independence_required"] is True


def test_m1_entry_manifest_contains_all_condition_6_identities(tmp_path: Path) -> None:
    output = tmp_path / "m1-entry-build-manifest.json"
    result = _run(
        str(DEV),
        "m1-entry-manifest",
        "--profile",
        _profile(),
        "--output",
        str(output),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == "TPAA_M1_ENTRY_BUILD_MANIFEST_V1"
    assert payload["status"] == "FROZEN_ENTRY_CANDIDATE"
    assert payload["admission"] == "M1_NOT_ADMITTED_BY_THIS_MANIFEST"
    assert payload["core_baseline"] == "CB-1.4.0"
    assert payload["db_schema_version"] == "1.6.0"
    assert len(payload["source_revision"]) == 40
    for key in (
        "baseline_lock_sha256",
        "dependency_lock_sha256",
        "p1_metric_catalog_sha256",
        "stage_authority_sha256",
        "dto_authority_sha256",
    ):
        assert len(payload[key]) == 64


def test_m1_entry_preparation_is_available_through_unified_cli() -> None:
    result = _run(str(DEV), "verify-m1-entry-preparation")
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"
    assert evidence["admission"] == "M1_NOT_ADMITTED"
