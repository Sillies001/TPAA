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


def test_m2_met_007_incremental_batch_replay_is_honest_and_exact(
    tmp_path: Path,
) -> None:
    path = tmp_path / "batch-replay.json"
    completed = _run(
        "m2-batch-replay-incremental-check",
        "--evidence",
        str(path),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    evidence = json.loads(path.read_text(encoding="utf-8"))

    assert evidence["schema"] == "TPAA_M2_MET_007_BATCH_REPLAY_INCREMENTAL_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-MET-007"
    assert evidence["tracking_issue"] == 97
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is False
    assert evidence["blocked_predecessors"] == [
        "M2-MET-002",
        "M2-MET-005",
        "M2-MET-006",
    ]
    assert evidence["failed_acceptance"] == []
    assert all(evidence["acceptance"].values())
    assert evidence["scope"] == {
        "business_metric_semantics_executed": False,
        "synthetic_runtime_probe_only": True,
        "execution_identity_lineage_only": True,
        "registry_lineage_binding_only": True,
        "per_metric_authority_lineage_binding_only": True,
        "input_payload_lineage_binding_only": True,
        "version_qualified_plugin_dispatch_only": True,
        "governed_dependency_lineage_only": True,
        "formal_32_metric_replay_claimed": False,
        "authority_values_invented": False,
    }

    product = evidence["logical_product"]
    assert len(product["catalog_metric_codes"]) == 32
    assert len(product["execution_metric_codes"]) == 32
    assert product["dispatch_key"] == "algorithm_id+algorithm_version"
    assert len(product["batch_logical_hash"]) == 64
    assert len(product["tampered_batch_logical_hash"]) == 64
    assert product["batch_logical_hash"] != product["tampered_batch_logical_hash"]
    assert evidence["acceptance"]["dispatch_key_version_qualified"]
    assert evidence["acceptance"]["dependency_manifest_hash_binding_exact_32"]
    assert evidence["acceptance"]["record_identity_binding_exact_32"]
    assert evidence["acceptance"]["plugin_manifest_hash_well_formed"]
    assert evidence["acceptance"]["plugin_manifest_replay_exact"]
    assert evidence["acceptance"]["input_lineage_encoding_exact"]
    assert evidence["acceptance"]["input_payload_hash_binding_exact_32"]
    assert evidence["acceptance"]["authority_lineage_hash_binding_exact_32"]
    assert evidence["acceptance"]["tampered_input_payload_hash_changes"]
    assert evidence["acceptance"]["generated_metric_projection_hash_well_formed"]
    assert evidence["acceptance"]["execution_identity_hash_well_formed"]
    assert evidence["acceptance"]["registry_lineage_hashes_well_formed"]
    assert len(product["generated_metric_projection_sha256"]) == 64
    assert len(product["execution_identity_sha256"]) == 64
    assert len(product["plugin_manifest_hash"]) == 64
    assert len(product["plugin_identity_manifest"]) == 32
    assert all(item[1] != "UNVERSIONED" for item in product["plugin_identity_manifest"])
    assert product["input_lineage_encoding"] == "TPAA_M2_INPUT_LINEAGE_JSON_V1"
    assert all(len(value) == 64 for value in product["registry_authority_hashes"].values())
    assert len(product["per_metric_hashes"]) == 32
    for row in product["per_metric_hashes"]:
        assert row["semantic_id"]
        assert isinstance(row["semantic_version"], int)
        assert row["algorithm_id"]
        assert row["algorithm_version"]
        assert len(row["definition_hash"]) == 64
        assert len(row["authority_lineage_hash"]) == 64
        assert len(row["input_payload_hash"]) == 64
        assert len(row["dependency_manifest_hash"]) == 64
        assert len(row["probe_evidence_hash"]) == 64
        assert len(row["plugin_output_hash"]) == 64
        assert len(row["record_logical_hash"]) == 64


def test_m2_met_007_incremental_cross_platform_compare_is_revision_exact(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.json"
    checked = _run(
        "m2-batch-replay-incremental-check",
        "--evidence",
        str(source),
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    payload = json.loads(source.read_text(encoding="utf-8"))
    revision = payload["source_revision"]

    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"
    completed = _run(
        "m2-batch-replay-incremental-compare",
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
    assert evidence["schema"] == (
        "TPAA_M2_MET_007_BATCH_REPLAY_INCREMENTAL_CROSS_PLATFORM_EVIDENCE_V1"
    )
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is False
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
