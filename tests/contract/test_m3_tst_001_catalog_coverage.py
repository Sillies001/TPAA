from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tools" / "testing" / "m3_catalog_coverage_check.py"
BASELINE = ROOT / "docs" / "baseline" / "SDIB-1.2" / "M3_TASK_BASELINE.json"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECK), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_m3_tst_001_exact_catalog_coverage_and_applicability() -> None:
    checked = _run("check")
    assert checked.returncode == 0, checked.stdout + checked.stderr

    payload = json.loads(checked.stdout)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    assert payload["schema"] == "TPAA_M3_TST_001_CATALOG_COVERAGE_EVIDENCE_V1"
    assert payload["task_id"] == "M3-TST-001"
    assert payload["tracking_issue"] == 117
    assert payload["status"] == "PASS"
    assert payload["task_complete"] is True
    assert payload["implementation_complete"] is True
    assert payload["failed_acceptance"] == []
    assert all(payload["acceptance"].values())

    logical = payload["logical_product"]
    assert logical["catalog_total_count"] == 116
    assert logical["foundation_count"] == 32
    assert logical["remainder_count"] == 84
    assert logical["remainder_codes"] == baseline["catalog_delivery"]["metric_codes"]
    assert logical["remainder_namespace_counts"] == {
        "AIR": 36,
        "DL": 8,
        "ESM": 6,
        "FUS": 8,
        "ID": 12,
        "PSV": 7,
        "TRK": 7,
    }
    assert logical["remainder_family_counts"] == baseline["family_counts"]
    assert logical["m3_applicability_contracts"] == baseline["family_applicability"]
    assert len(logical["integrated_catalog_codes"]) == 116
    assert len(set(logical["integrated_catalog_codes"])) == 116
    assert set(logical["integrated_execution_codes"]) == set(
        logical["integrated_catalog_codes"]
    )

    assert payload["scope"]["business_metric_semantics_executed"] is False
    assert payload["scope"]["metric_values_recomputed"] is False
    assert payload["scope"]["publication_executed"] is False
    assert payload["scope"]["persistence_executed"] is False
    assert payload["scope"]["frozen_catalog_modified"] is False
    assert payload["scope"]["frozen_applicability_modified"] is False


def test_m3_tst_001_cross_platform_evidence_contract(tmp_path: Path) -> None:
    source = tmp_path / "catalog-coverage.json"
    checked = _run("check", "--evidence", str(source))
    assert checked.returncode == 0, checked.stdout + checked.stderr

    payload = json.loads(source.read_text(encoding="utf-8"))
    revision = payload["source_revision"]

    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"

    result = _run(
        "compare",
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
    assert evidence["schema"] == (
        "TPAA_M3_TST_001_CATALOG_COVERAGE_CROSS_PLATFORM_EVIDENCE_V1"
    )
    assert evidence["task_id"] == "M3-TST-001"
    assert evidence["tracking_issue"] == 117
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is True
    assert evidence["implementation_complete"] is True
    assert evidence["source_revision"] == revision
    assert evidence["windows_source_revision"] == revision
    assert evidence["linux_source_revision"] == revision
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
