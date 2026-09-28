from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tpaa_metric import (
    M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
    CatalogMetricEngine,
    M2MetricPluginRequest,
    MetricPluginRegistry,
    build_m3_metric_execution_plan,
)
from tpaa_observation import (
    M3ReleaseSnapshotError,
    build_m3_publication_routing_plan,
    build_m3_release_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
CHECK = ROOT / "tools" / "testing" / "m3_immutable_release_check.py"
SESSION_ID = "77777777-7777-4777-8777-777777777777"


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _products() -> tuple[object, object, object, dict[str, dict[str, object]]]:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    routing = build_m3_publication_routing_plan(AUTHORITY)
    registry = MetricPluginRegistry()

    def probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {
            "metric_code": request.definition.metric_code,
            "input_token": request.input_payload["input_token"],
        }

    for definition in plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m3-obs-002-test:{definition.metric_code}:v1",
            plugin=probe,
        )
    inputs = {
        definition.metric_code: {
            "input_token": definition.metric_code,
        }
        for definition in plan.definitions
    }
    batch = CatalogMetricEngine(
        plan,
        registry,
        operator_implementations=M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
    ).execute(
        inputs,
        validate_runtime_contract=False,
    )
    evidence = {
        definition.metric_code: {
            "evidence_contract": "M3_RELEASE_EVIDENCE_BINDING_V1",
            "metric_code": definition.metric_code,
        }
        for definition in plan.definitions
    }
    return plan, routing, batch, evidence


def test_m3_obs_002_freezes_exact_116_release_bound_snapshot() -> None:
    plan, routing, batch, evidence = _products()
    request_hash = _hash({"session_id": SESSION_ID, "command": "snapshot"})
    context = {
        "context_id": "88888888-8888-4888-8888-888888888888",
        "context_version": "V1",
    }
    snapshot = build_m3_release_snapshot(
        session_id=SESSION_ID,
        request_hash=request_hash,
        release_no=1,
        parent_release_id=None,
        plan=plan,  # type: ignore[arg-type]
        routing=routing,  # type: ignore[arg-type]
        batch=batch,  # type: ignore[arg-type]
        evidence_by_metric=evidence,
        context_snapshot=context,
        world_snapshot={"world_product_hash": "3" * 64},
        identity_snapshot={"subject_binding_hash": "4" * 64},
        provenance_snapshot={"source_hash": "5" * 64},
    )
    frozen_context = snapshot.bindings.context_json
    frozen_evidence = snapshot.evidence(snapshot.metric_codes[0]).evidence_json
    context["context_version"] = "MUTATED"
    evidence[snapshot.metric_codes[0]]["evidence_contract"] = "MUTATED"

    assert len(snapshot.definitions) == 116
    assert len(snapshot.execution_records) == 116
    assert len(snapshot.evidence_bindings) == 116
    assert snapshot.metric_codes == plan.metric_codes  # type: ignore[union-attr]
    assert snapshot.catalog_hash == plan.catalog_sha256  # type: ignore[union-attr]
    assert snapshot.metric_execution_plan_hash == plan.logical_hash  # type: ignore[union-attr]
    assert snapshot.publication_routing_plan_hash == routing.logical_hash  # type: ignore[union-attr]
    assert snapshot.execution_batch_hash == batch.logical_hash  # type: ignore[union-attr]
    assert snapshot.bindings.context_json == frozen_context
    assert "MUTATED" not in snapshot.bindings.context_json
    assert snapshot.evidence(snapshot.metric_codes[0]).evidence_json == frozen_evidence
    assert "MUTATED" not in snapshot.evidence(snapshot.metric_codes[0]).evidence_json
    assert len(snapshot.manifest_hash) == 64
    assert snapshot.status == "VALIDATED"


def test_m3_obs_002_rejects_missing_evidence_and_batch_drift() -> None:
    plan, routing, batch, evidence = _products()
    missing = dict(evidence)
    missing.pop(next(iter(missing)))
    with pytest.raises(M3ReleaseSnapshotError) as missing_error:
        build_m3_release_snapshot(
            session_id=SESSION_ID,
            request_hash="6" * 64,
            release_no=1,
            parent_release_id=None,
            plan=plan,  # type: ignore[arg-type]
            routing=routing,  # type: ignore[arg-type]
            batch=batch,  # type: ignore[arg-type]
            evidence_by_metric=missing,
            context_snapshot={"context": "v1"},
            world_snapshot={"world": "v1"},
            identity_snapshot={"identity": "v1"},
            provenance_snapshot={"provenance": "v1"},
        )
    assert missing_error.value.code == "M3_RELEASE_EVIDENCE_MEMBERSHIP_INVALID"

    with pytest.raises(M3ReleaseSnapshotError) as batch_error:
        build_m3_release_snapshot(
            session_id=SESSION_ID,
            request_hash="6" * 64,
            release_no=1,
            parent_release_id=None,
            plan=plan,  # type: ignore[arg-type]
            routing=routing,  # type: ignore[arg-type]
            batch=replace(batch, plan_hash="0" * 64),  # type: ignore[arg-type]
            evidence_by_metric=evidence,
            context_snapshot={"context": "v1"},
            world_snapshot={"world": "v1"},
            identity_snapshot={"identity": "v1"},
            provenance_snapshot={"provenance": "v1"},
        )
    assert batch_error.value.code == "M3_RELEASE_BATCH_PLAN_MISMATCH"


def test_m3_obs_002_evidence_and_cross_platform_contract(
    tmp_path: Path,
) -> None:
    source = tmp_path / "release.json"
    checked = subprocess.run(
        [
            sys.executable,
            str(CHECK),
            "check",
            "--evidence",
            str(source),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    payload = json.loads(source.read_text(encoding="utf-8"))
    assert payload["schema"] == "TPAA_M3_OBS_002_IMMUTABLE_RELEASE_EVIDENCE_V1"
    assert payload["task_id"] == "M3-OBS-002"
    assert payload["tracking_issue"] == 116
    assert payload["status"] == "PASS"
    assert payload["task_complete"] is True
    assert payload["implementation_complete"] is True
    assert payload["failed_acceptance"] == []
    assert all(payload["acceptance"].values())
    product = payload["logical_product"]
    assert len(product["definitions"]) == 116
    assert len(product["execution_records"]) == 116
    assert len(product["evidence_bindings"]) == 116
    assert len(product["manifest_hash"]) == 64
    assert payload["scope"]["latest_authority_resolution_used"] is False
    assert payload["scope"]["current_authority_resolution_used"] is False

    revision = payload["source_revision"]
    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"
    result = subprocess.run(
        [
            sys.executable,
            str(CHECK),
            "compare",
            "--windows",
            str(windows),
            "--linux",
            str(linux),
            "--expected-revision",
            revision,
            "--evidence",
            str(compared),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    evidence_result = json.loads(compared.read_text(encoding="utf-8"))
    assert evidence_result["schema"] == (
        "TPAA_M3_OBS_002_IMMUTABLE_RELEASE_CROSS_PLATFORM_EVIDENCE_V1"
    )
    assert evidence_result["status"] == "PASS"
    assert evidence_result["task_complete"] is True
    assert evidence_result["implementation_complete"] is True
    assert evidence_result["failed_acceptance"] == []
    assert all(evidence_result["checks"].values())
