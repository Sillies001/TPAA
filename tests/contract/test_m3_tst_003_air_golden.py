from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tools" / "testing" / "m3_air_golden_check.py"

EXPECTED_STRUCTURED = {
    "P1-AIR-007",
    "P1-AIR-019",
    "P1-AIR-025",
    "P1-AIR-030",
    "P1-AIR-035",
    "P1-AIR-039",
}


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECK), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_m3_tst_003_air_golden_negative_contract() -> None:
    checked = _run("check")
    assert checked.returncode == 0, checked.stdout + checked.stderr

    payload = json.loads(checked.stdout)
    assert payload["schema"] == "TPAA_M3_TST_003_AIR_GOLDEN_NEGATIVE_EVIDENCE_V1"
    assert payload["task_id"] == "M3-TST-003"
    assert payload["tracking_issue"] == 117
    assert payload["status"] == "PASS"
    assert payload["task_complete"] is True
    assert payload["implementation_complete"] is True
    assert payload["failed_acceptance"] == []
    assert all(payload["acceptance"].values())

    logical = payload["logical_product"]
    assert len(logical["metric_codes"]) == 36
    assert logical["metric_codes"] == [
        f"P1-AIR-{index:03d}" for index in range(4, 40)
    ]
    assert len(logical["numeric_metric_codes"]) == 30
    assert set(logical["structured_metric_codes"]) == EXPECTED_STRUCTURED
    assert set(logical["structured_schema_ids"]) == EXPECTED_STRUCTURED
    assert set(logical["structured_schema_hashes"]) == EXPECTED_STRUCTURED
    assert set(logical["structured_schema_negative_codes"]) == EXPECTED_STRUCTURED
    assert set(logical["structured_schema_negative_codes"].values()) == {
        "M2_METRIC_STRUCTURED_OUTPUT_SCHEMA_VIOLATION"
    }

    assert logical["quality_partial_case"]["status"] == "VALID"
    assert (
        logical["quality_partial_case"]["value_structured"][
            "median_energy_rate_status"
        ]
        == "INSUFFICIENT_RATE_SAMPLES"
    )
    assert logical["insufficient_case"]["status"] == "INSUFFICIENT_DATA"
    assert logical["invalid_case"]["error_code"] == "M2_METRIC_PLUGIN_OUTPUT_INVALID"

    assert payload["scope"]["shared_catalog_metric_engine_only"] is True
    assert payload["scope"]["six_structured_schemas_independently_checked"] is True
    assert payload["scope"]["catalog_formulas_modified"] is False
    assert payload["scope"]["applicability_modified"] is False
    assert payload["scope"]["publication_routes_modified"] is False
    assert payload["scope"]["persistence_executed"] is False


def test_m3_tst_003_cross_platform_evidence_contract(tmp_path: Path) -> None:
    source = tmp_path / "air-golden.json"
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
        "TPAA_M3_TST_003_AIR_GOLDEN_NEGATIVE_"
        "CROSS_PLATFORM_EVIDENCE_V1"
    )
    assert evidence["task_id"] == "M3-TST-003"
    assert evidence["tracking_issue"] == 117
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is True
    assert evidence["implementation_complete"] is True
    assert evidence["source_revision"] == revision
    assert evidence["windows_source_revision"] == revision
    assert evidence["linux_source_revision"] == revision
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
