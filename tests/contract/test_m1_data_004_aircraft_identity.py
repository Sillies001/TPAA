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


def test_m1_data_004_acceptance_command_emits_machine_evidence(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "aircraft-identity.json"
    result = _run(
        "m1-aircraft-identity-check",
        "--evidence",
        str(evidence_path),
    )
    assert result.returncode == 0, result.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M1_DATA_004_AIRCRAFT_IDENTITY_EVIDENCE_V1"
    assert evidence["task_id"] == "M1-DATA-004"
    assert evidence["status"] == "PASS"
    assert evidence["resolution_count"] == 8
    assert evidence["unique_governed_aircraft_id_count"] == 1
    assert evidence["unique_replay_basis_hash_count"] == 8
    assert evidence["unique_logical_hash_count"] == 8
    assert evidence["replay_stable"] is True
    assert evidence["identity_field"] == "aircraft_id"
    assert evidence["source_alias_role"] == "LINEAGE_ONLY"
    assert evidence["source_alias_used_as_business_identity"] is False
    assert evidence["business_identity_generated_from_alias"] is False
    assert evidence["resolution_method"] == "GOVERNED_FIXTURE_AIRCRAFT_ID"
    assert evidence["master_aircraft_persistence_executed"] is False
    assert evidence["aircraft_instance_projection_executed"] is False
    assert evidence["canonical_flight_channel_projection_executed"] is False
    assert evidence["evaluation_context_binding_executed"] is False
    assert evidence["stage_projection_executed"] is False
    assert evidence["metric_logic_executed"] is False


def test_m1_data_004_nominal_evidence_keeps_source_alias_lineage_only() -> None:
    result = _run("m1-aircraft-identity-check")
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)

    records = evidence["records"]
    assert isinstance(records, list)
    nominal = next(
        record
        for record in records
        if record["fixture_id"] == "BF_M1_NOMINAL_V1"
    )

    assert nominal["aircraft_id"] == "22222222-2222-4222-8222-222222222222"
    assert nominal["source_aircraft_key"] == "SYNTH-ACFT-01"
    assert nominal["identity_field"] == "aircraft_id"
    assert nominal["source_alias_role"] == "LINEAGE_ONLY"
    assert len(nominal["source_artifact_sha256"]) == 64
    assert len(nominal["context_artifact_sha256"]) == 64
    assert len(nominal["replay_basis_sha256"]) == 64
    assert len(nominal["logical_hash"]) == 64
