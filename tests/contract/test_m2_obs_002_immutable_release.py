from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tpaa_metric import (
    CatalogMetricEngine,
    M2MetricPluginRequest,
    MetricPluginRegistry,
    build_m2_metric_execution_plan,
)
from tpaa_observation import (
    M2ReleaseSnapshotError,
    build_m2_publication_routing_plan,
    build_m2_release_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"
SESSION_ID = "11111111-1111-4111-8111-111111111111"


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


def _batch() -> tuple[object, object, object]:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    routing = build_m2_publication_routing_plan(AUTHORITY)
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
            plugin_id=f"m2-obs-002-test:{definition.metric_code}:v1",
            plugin=probe,
        )
    inputs = {
        definition.metric_code: {
            "input_token": definition.metric_code,
        }
        for definition in plan.definitions
    }
    batch = CatalogMetricEngine(plan, registry).execute(
        inputs,
        validate_runtime_contract=False,
    )
    return plan, routing, batch


def test_m2_obs_002_freezes_exact_release_bound_foundation_snapshot() -> None:
    plan, routing, batch = _batch()
    request_hash = _hash({"session_id": SESSION_ID, "command": "snapshot"})
    context = {
        "context_id": "22222222-2222-4222-8222-222222222222",
        "context_version": "V1",
    }
    snapshot = build_m2_release_snapshot(
        session_id=SESSION_ID,
        request_hash=request_hash,
        release_no=1,
        parent_release_id=None,
        plan=plan,  # type: ignore[arg-type]
        routing=routing,  # type: ignore[arg-type]
        batch=batch,  # type: ignore[arg-type]
        context_snapshot=context,
        world_snapshot={"world_product_hash": "3" * 64},
        identity_snapshot={"subject_binding_hash": "4" * 64},
        provenance_snapshot={"source_hash": "5" * 64},
    )
    frozen_context = snapshot.bindings.context_json
    context["context_version"] = "MUTATED"

    assert len(snapshot.definitions) == 32
    assert len(snapshot.execution_records) == 32
    assert snapshot.metric_codes == plan.metric_codes  # type: ignore[union-attr]
    assert snapshot.catalog_hash == plan.catalog_sha256  # type: ignore[union-attr]
    assert snapshot.metric_execution_plan_hash == plan.logical_hash  # type: ignore[union-attr]
    assert snapshot.publication_routing_plan_hash == routing.logical_hash  # type: ignore[union-attr]
    assert snapshot.execution_batch_hash == batch.logical_hash  # type: ignore[union-attr]
    assert snapshot.bindings.context_json == frozen_context
    assert "MUTATED" not in snapshot.bindings.context_json
    assert len(snapshot.manifest_hash) == 64
    assert snapshot.status == "VALIDATED"


def test_m2_obs_002_rejects_execution_plan_drift() -> None:
    plan, routing, batch = _batch()
    with pytest.raises(M2ReleaseSnapshotError) as error:
        build_m2_release_snapshot(
            session_id=SESSION_ID,
            request_hash="6" * 64,
            release_no=1,
            parent_release_id=None,
            plan=plan,  # type: ignore[arg-type]
            routing=routing,  # type: ignore[arg-type]
            batch=replace(batch, plan_hash="0" * 64),  # type: ignore[arg-type]
            context_snapshot={"context": "v1"},
            world_snapshot={"world": "v1"},
            identity_snapshot={"identity": "v1"},
            provenance_snapshot={"provenance": "v1"},
        )
    assert error.value.code == "M2_RELEASE_BATCH_PLAN_MISMATCH"


def test_m2_obs_002_evidence_and_cross_platform_contract(tmp_path: Path) -> None:
    source = tmp_path / "release.json"
    checked = subprocess.run(
        [
            sys.executable,
            str(DEV),
            "m2-immutable-release-check",
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
    assert payload["schema"] == "TPAA_M2_OBS_002_IMMUTABLE_RELEASE_EVIDENCE_V1"
    assert payload["task_id"] == "M2-OBS-002"
    assert payload["tracking_issue"] == 98
    assert payload["status"] == "PASS"
    assert payload["task_complete"] is True
    assert payload["implementation_complete"] is True
    assert payload["failed_acceptance"] == []
    assert all(payload["acceptance"].values())
    product = payload["logical_product"]
    assert len(product["definitions"]) == 32
    assert len(product["execution_records"]) == 32
    assert len(product["manifest_hash"]) == 64
    assert payload["scope"]["latest_authority_resolution_used"] is False
    assert payload["scope"]["database_persistence_executed"] is False

    revision = payload["source_revision"]
    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"
    result = subprocess.run(
        [
            sys.executable,
            str(DEV),
            "m2-immutable-release-compare",
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
    evidence = json.loads(compared.read_text(encoding="utf-8"))
    assert evidence["schema"] == (
        "TPAA_M2_OBS_002_IMMUTABLE_RELEASE_CROSS_PLATFORM_EVIDENCE_V1"
    )
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is True
    assert evidence["implementation_complete"] is True
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
