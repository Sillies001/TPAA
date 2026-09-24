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


def test_m1_data_002_acceptance_command_emits_machine_evidence(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "source-registry.json"
    result = _run(
        "m1-source-registry-check",
        "--evidence",
        str(evidence_path),
    )
    assert result.returncode == 0, result.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M1_DATA_002_SOURCE_REGISTRY_EVIDENCE_V1"
    assert evidence["task_id"] == "M1-DATA-002"
    assert evidence["status"] == "PASS"
    assert evidence["registration_count"] == 8
    assert evidence["registry_ref_count"] == 24
    assert evidence["unique_bundle_ref_count"] == 8
    assert evidence["unique_context_ref_count"] == 8
    assert evidence["immutable_refs_verified"] is True
    assert evidence["database_persistence_executed"] is False
    assert evidence["session_time_transform_executed"] is False
    assert evidence["canonical_projection_executed"] is False
    assert evidence["evaluation_context_binding_executed"] is False
    assert evidence["canonical_context_artifact_kind_invented"] is False
    assert evidence["context_binding_deferred_to"] == "M1-DATA-006"


def test_m1_data_002_records_bind_hashes_into_immutable_refs() -> None:
    result = _run("m1-source-registry-check")
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)

    records = evidence["records"]
    assert isinstance(records, list)
    assert len(records) == 8
    for record in records:
        assert record["bundle_sha256"] in record["bundle_ref"]
        assert record["source_artifact_sha256"] in record["source_artifact_ref"]
        assert record["context_artifact_sha256"] in record["context_artifact_ref"]
        assert record["bundle_immutable"] is True
        assert record["source_artifact_immutable"] is True
        assert record["context_artifact_immutable"] is True
