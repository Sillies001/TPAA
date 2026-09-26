from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"
SNS_CODES = [f"P1-SNS-{index:03d}" for index in range(5, 22)]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_m2_met_005_incremental_evidence_is_honest_and_complete_for_algorithms(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sns-accuracy.json"
    completed = _run("m2-sns-accuracy-incremental-check", "--evidence", str(path))
    assert completed.returncode == 0, completed.stdout + completed.stderr
    evidence = json.loads(path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M2_MET_005_SNS_ACCURACY_INCREMENTAL_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-MET-005"
    assert evidence["tracking_issue"] == 97
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is False
    assert evidence["implementation_complete"] is True
    assert evidence["formal_completion_blocked_by_authority"] is False
    assert evidence["formal_completion_blocked_by_profile_integration"] is True
    assert evidence["failed_acceptance"] == []
    assert all(evidence["acceptance"].values())
    assert evidence["authority_gaps"] == {}
    assert (
        evidence["invalid_qa_payload_error_code"]
        == "M2_METRIC_PLUGIN_OUTPUT_INVALID"
    )
    assert evidence["logical_product"]["delivery_membership"] == SNS_CODES
    assert set(evidence["logical_product"]["definition_hashes"]) == set(SNS_CODES)
    assert evidence["acceptance"]["version_qualified_plugin_identity_exact"]
    assert evidence["acceptance"]["discriminating_aggregation_golden_exact_17"]
    assert evidence["acceptance"]["catalog_profile_required_fields_exact"]
    assert evidence["acceptance"]["catalog_error_domain_map_exact_17"]
    assert evidence["acceptance"]["runtime_transport_validation_exact_17"]
    assert evidence["acceptance"]["full_profile_rejection_reason_surface_exact"]
    assert evidence["acceptance"]["profile_component_cap_rule_exact"]
    assert evidence["acceptance"]["rejected_samples_excluded_from_statistics"]
    assert evidence["acceptance"]["empty_sample_set_uses_profile_reason"]
    assert evidence["acceptance"]["profile_provenance_persisted_exact_17"]
    assert evidence["acceptance"]["profile_identity_change_segments_evidence"]
    assert evidence["scope"]["authority_independent_algorithms_executed"] is True
    assert evidence["scope"]["approved_c3_authority_available"] is True
    assert evidence["scope"]["approved_c3_profile_consumed"] is False
    assert evidence["scope"]["adopted_qa_semantics_executed_by_this_check"] is False
    assert evidence["scope"]["formal_task_completion_claimed"] is False
    manifest = evidence["logical_product"]["plugin_identity_manifest"]
    assert len(manifest) == 17
    assert all(item[1] != "UNVERSIONED" for item in manifest)


def test_m2_met_005_incremental_cross_platform_compare_is_revision_exact(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.json"
    checked = _run("m2-sns-accuracy-incremental-check", "--evidence", str(source))
    assert checked.returncode == 0, checked.stdout + checked.stderr
    payload = json.loads(source.read_text(encoding="utf-8"))
    revision = payload["source_revision"]
    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"
    completed = _run(
        "m2-sns-accuracy-incremental-compare",
        "--windows",
        str(windows),
        "--linux",
        str(linux),
        "--expected-revision",
        revision,
        "--evidence",
        str(compared),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    evidence = json.loads(compared.read_text(encoding="utf-8"))
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is False
    assert evidence["implementation_complete"] is True
    assert evidence["formal_completion_blocked_by_authority"] is False
    assert evidence["formal_completion_blocked_by_profile_integration"] is True
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
