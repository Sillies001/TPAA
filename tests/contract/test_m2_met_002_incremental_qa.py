from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_m2_met_002_incremental_contract_keeps_task_open(tmp_path: Path) -> None:
    evidence_path = tmp_path / "qa.json"
    completed = _run(
        "m2-qa-foundation-incremental-check",
        "--evidence",
        str(evidence_path),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M2_MET_002_INCREMENTAL_QA_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-MET-002"
    assert evidence["tracking_issue"] == 97
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is False
    assert evidence["failed_acceptance"] == []
    assert set(evidence["authority_gaps"]) == {"P1-QA-001", "P1-QA-002"}
    assert set(evidence["dependency_effects"]) == {"P1-QA-006"}
    assert evidence["acceptance"]["registry_uses_catalog_algorithm_identities_exact"]
    assert evidence["acceptance"]["safe_subset_executes_through_general_engine"]
    product = evidence["logical_product"]
    assert product["dispatch_key"] == "algorithm_id+algorithm_version"
    assert all(
        record["algorithm_version"] and len(record["dependency_manifest_hash"]) == 64
        for record in product["safe_engine_records"]
    )
    assert evidence["blocked_error_codes"] == {
        "P1-QA-001": "M2_QA_AUTHORITY_GAP",
        "P1-QA-002": "M2_QA_AUTHORITY_GAP",
        "P1-QA-006": "M2_QA_AUTHORITY_GAP",
    }


def test_m2_met_002_cross_platform_compare_is_revision_exact(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    checked = _run(
        "m2-qa-foundation-incremental-check",
        "--evidence",
        str(source),
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    payload = json.loads(source.read_text(encoding="utf-8"))
    revision = payload["source_revision"]
    assert isinstance(revision, str)

    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compare.json"
    result = _run(
        "m2-qa-foundation-incremental-compare",
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
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is False
    assert evidence["failed_acceptance"] == []
