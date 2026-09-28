from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tools" / "testing" / "m3_product_layer_golden_check.py"

EXPECTED_COUNTS = {
    "TRK": 7,
    "ID": 12,
    "PSV": 7,
    "ESM": 6,
    "DL": 8,
    "FUS": 8,
}


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECK), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=360,
    )


def test_m3_tst_004_product_layer_golden_applicability_contract() -> None:
    checked = _run("check")
    assert checked.returncode == 0, checked.stdout + checked.stderr

    payload = json.loads(checked.stdout)
    assert payload["schema"] == "TPAA_M3_TST_004_PRODUCT_LAYER_GOLDEN_EVIDENCE_V1"
    assert payload["task_id"] == "M3-TST-004"
    assert payload["tracking_issue"] == 117
    assert payload["status"] == "PASS"
    assert payload["task_complete"] is True
    assert payload["implementation_complete"] is True
    assert payload["failed_acceptance"] == []
    assert all(payload["acceptance"].values())

    logical = payload["logical_product"]
    assert logical["family_counts"] == EXPECTED_COUNTS
    assert len(logical["combined_metric_codes"]) == 48
    assert len(set(logical["combined_metric_codes"])) == 48
    for family, count in EXPECTED_COUNTS.items():
        assert len(logical["family_metric_codes"][family]) == count
        assert set(logical["golden_metric_codes"][family]) == set(
            logical["family_metric_codes"][family]
        )
        assert logical["applicability_checks"][family]
        assert logical["negative_no_fake_observation_checks"][family]

    assert payload["scope"]["shared_catalog_metric_engine_only"] is True
    assert payload["scope"]["wrong_product_system_no_fake_observation_enforced"] is True
    assert payload["scope"]["catalog_formulas_modified"] is False
    assert payload["scope"]["applicability_modified"] is False
    assert payload["scope"]["publication_routes_modified"] is False
    assert payload["scope"]["persistence_executed"] is False
    assert payload["scope"]["publication_executed"] is False


def test_m3_tst_004_cross_platform_evidence_contract(tmp_path: Path) -> None:
    source = tmp_path / "product-layer-golden.json"
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
        "TPAA_M3_TST_004_PRODUCT_LAYER_GOLDEN_"
        "CROSS_PLATFORM_EVIDENCE_V1"
    )
    assert evidence["task_id"] == "M3-TST-004"
    assert evidence["tracking_issue"] == 117
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is True
    assert evidence["implementation_complete"] is True
    assert evidence["source_revision"] == revision
    assert evidence["windows_source_revision"] == revision
    assert evidence["linux_source_revision"] == revision
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
