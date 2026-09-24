from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tpaa_ingest import GOVERNED_FIXTURE_IDS, load_synthetic_fixture_bundle

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "m1"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_all_governed_bundles_load_through_source_adapter() -> None:
    refs: set[str] = set()
    for fixture_id in sorted(GOVERNED_FIXTURE_IDS):
        bundle = load_synthetic_fixture_bundle(FIXTURE_ROOT / fixture_id)
        assert bundle.identity.fixture_id == fixture_id
        assert bundle.data_classification == "SYNTHETIC"
        assert bundle.mapping_version == "M1_BASIC_FLIGHT_SOURCE_MAP_V1"
        assert bundle.session.source_time_basis == "SOURCE_US"
        refs.add(bundle.identity.stable_source_ref)

    assert len(refs) == 8


def test_source_adapter_acceptance_command_emits_machine_evidence(tmp_path: Path) -> None:
    evidence_path = tmp_path / "source-adapter.json"
    result = _run(
        "m1-source-adapter-check",
        "--evidence",
        str(evidence_path),
    )
    assert result.returncode == 0, result.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M1_DATA_001_SOURCE_ADAPTER_EVIDENCE_V1"
    assert evidence["task_id"] == "M1-DATA-001"
    assert evidence["status"] == "PASS"
    assert evidence["bundle_count"] == 8
    assert evidence["unique_source_ref_count"] == 8
    assert evidence["mapping_version"] == "M1_BASIC_FLIGHT_SOURCE_MAP_V1"
    assert evidence["source_clock_preserved"] is True
    assert evidence["session_time_transform_executed"] is False
    assert evidence["canonical_projection_executed"] is False
    assert evidence["stage_projection_executed"] is False
    assert evidence["metric_logic_executed"] is False


def test_source_adapter_preserves_partial_missing_values_as_none() -> None:
    bundle = load_synthetic_fixture_bundle(
        FIXTURE_ROOT / "BF_M1_STRUCTURED_PARTIAL_V1"
    )
    assert bundle.rows[0].values["mach"] is None
    assert bundle.rows[1].values["tas"] is None
