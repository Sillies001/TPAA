from __future__ import annotations

import os
from typing import Any, cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tpaa_api.runtime import register_product_runtime_routes
from tpaa_application import (
    ApplicationService,
    W7ExternalCapability,
    W7ExternalCapabilityError,
    W7ExternalCapabilityRegistry,
)
from tpaa_gui.product_shell import create_product_workspace
from tpaa_gui.w7_projection import (
    W7ProjectionError,
    build_capability_gate,
    build_model_registry_projection,
    build_upper_product_projection,
    local_external_capability_gates,
)

SNAPSHOT = "11111111-1111-4111-8111-111111111111"
RELEASE = "22222222-2222-4222-8222-222222222222"
MODEL = "33333333-3333-4333-8333-333333333333"
HASH = "a" * 64


def _upper(kind: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "TPAA_ED2_UPPER_PRODUCT_PROJECTION_V1",
        "snapshot_id": SNAPSHOT,
        "kind": kind,
        "source_release_ids": [RELEASE],
        "as_of_utc": "2026-10-25T00:00:00Z",
        "logical_content_hash": HASH,
        "payload": payload,
        "frozen": True,
        "mutable_alias_resolution": False,
    }


def test_w7_course_and_joint_lvc_snapshots_are_exact_and_fail_closed() -> None:
    course = build_upper_product_projection(
        _upper(
            "COURSE_UNIT_ANALYTICS",
            {
                "scope_kind": "COURSE",
                "privacy_mode": "AGGREGATED",
                "minimum_cohort_size": 4,
                "cohort_size": 8,
                "result_state": "PUBLISHED",
                "suppressed_below_minimum": True,
            },
        ),
        expected_snapshot_id=SNAPSHOT,
        expected_kind="COURSE_UNIT_ANALYTICS",
    )
    assert course.snapshot_id == SNAPSHOT

    gateway = build_upper_product_projection(
        _upper(
            "JOINT_LVC_GATEWAY",
            {
                "external_protocol_boundary": True,
                "session_type": "LVC",
                "mapping_lossless": True,
                "fact_projection_separated": True,
                "operational_optimization": False,
                "mapping_profile_sha256": HASH,
                "interop_snapshot_id": f"P6_INTEROP_SHA256:{HASH}",
            },
        ),
        expected_snapshot_id=SNAPSHOT,
        expected_kind="JOINT_LVC_GATEWAY",
    )
    assert gateway.payload["fact_projection_separated"] is True

    conflated = _upper(
        "JOINT_LVC_GATEWAY",
        {
            **dict(gateway.payload),
            "fact_projection_separated": False,
        },
    )
    with pytest.raises(W7ProjectionError, match="GATEWAY_CONTRACT_INVALID"):
        build_upper_product_projection(
            conflated,
            expected_snapshot_id=SNAPSHOT,
            expected_kind="JOINT_LVC_GATEWAY",
        )
    with pytest.raises(W7ProjectionError, match="MUTABLE_ALIAS"):
        build_upper_product_projection(
            _upper("COURSE_UNIT_ANALYTICS", dict(course.payload)),
            expected_snapshot_id="latest",
            expected_kind="COURSE_UNIT_ANALYTICS",
        )


def test_w7_external_actions_require_endpoint_and_acceptance_hash() -> None:
    gates = local_external_capability_gates()
    assert len(gates) == 4
    assert all(not gate.action_enabled for gate in gates)
    assert {gate.state for gate in gates} == {"NOT_CONFIGURED"}

    accepted = build_capability_gate(
        {
            "capability": "JOINT_LVC_LIVE_GATEWAY",
            "state": "AVAILABLE",
            "reason_code": "STAGING_ACCEPTANCE_PASSED",
            "endpoint_ref": "staging://joint-lvc/gateway-01",
            "acceptance_evidence_sha256": HASH,
        }
    )
    assert accepted.action_enabled is True
    assert accepted.acceptance_evidence_sha256 == HASH

    with pytest.raises(W7ProjectionError, match="SHA256_INVALID"):
        build_capability_gate(
            {
                "capability": "JOINT_LVC_LIVE_GATEWAY",
                "state": "AVAILABLE",
                "reason_code": "STAGING_ACCEPTANCE_PASSED",
                "endpoint_ref": "staging://joint-lvc/gateway-01",
                "acceptance_evidence_sha256": "not-evidence",
            }
        )


def test_w7_runtime_gate_is_machine_readable_and_rejects_false_activation() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    registry = W7ExternalCapabilityRegistry.local_closed()

    class _UnusedStorage:
        def execute(self) -> Any:
            raise AssertionError("storage is outside the W7 gate read")

    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),
        w7_external_capabilities=registry,
    )
    client = TestClient(register_product_runtime_routes(FastAPI(), application))
    response = client.get("/runtime/external-capabilities")
    assert response.status_code == 200
    assert response.json()["schema"] == ("TPAA_W7_EXTERNAL_CAPABILITY_AVAILABILITY_V1")
    assert response.json()["all_external_actions_gated"] is True
    assert all(item["action_enabled"] is False for item in response.json()["items"])

    with pytest.raises(W7ExternalCapabilityError, match="ACCEPTANCE_EVIDENCE_REQUIRED"):
        W7ExternalCapability(
            capability="JOINT_LVC_LIVE_GATEWAY",
            state="AVAILABLE",
            reason_code="UNPROVEN",
            endpoint_ref="staging://joint-lvc/unapproved",
        )


def test_w7_model_registry_projects_qualified_evidence_without_recompute() -> None:
    model = build_model_registry_projection(
        {
            "capability_model_id": MODEL,
            "status": "VALIDATED",
            "validation_status": "VALIDATED",
            "applicability_status": "APPLICABLE",
            "calibration_status": "CALIBRATED",
            "release_state": "CANDIDATE_NOT_ADMITTED",
            "plugin_name": "p6-linear",
            "plugin_version": "1.0.0",
            "model_artifact_hash": HASH,
        },
        expected_model_id=MODEL,
    )
    assert model.plugin_identity == "p6-linear@1.0.0"
    assert model.calibration_status == "CALIBRATED"
    with pytest.raises(W7ProjectionError, match="EXACT_ID_MISMATCH"):
        build_model_registry_projection(
            {
                "capability_model_id": MODEL,
                "status": "VALIDATED",
                "validation_status": "VALIDATED",
                "applicability_status": "APPLICABLE",
                "calibration_status": "CALIBRATED",
                "release_state": "CANDIDATE_NOT_ADMITTED",
                "plugin_name": "p6-linear",
                "plugin_version": "1.0.0",
                "model_artifact_hash": HASH,
            },
            expected_model_id=RELEASE,
        )


def test_w7_shell_maps_p11_to_four_independent_workspaces_and_hard_gates() -> None:
    pytest.importorskip("PySide6")
    from PySide6 import QtCore, QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(["w7-test"])

    def diagnostics() -> Any:
        from tpaa_gui.diagnostics import DiagnosticsSnapshot

        return DiagnosticsSnapshot(
            readiness="READY",
            backend_state="READY",
            mismatches=(),
            failure_code=None,
            expected=None,
            observed=None,
        )

    root = create_product_workspace(
        QtCore,
        QtWidgets,
        None,
        transport=cast(Any, object()),
        diagnostics_provider=diagnostics,
    )
    page = root._tpaa_pages[10]
    content = page._tpaa_content
    assert content.objectName() == "tpaaP11Content"
    assert content.property("tpaaOriginalObjectName") == "tpaaP11Workflow"
    tabs = root.findChild(QtWidgets.QTabWidget, "tpaaP11Workspaces")
    assert tabs is not None
    assert tabs.count() == 4
    for lane in (
        "tpaaP11ActualLane",
        "tpaaP11ForecastLane",
        "tpaaP11CounterfactualLane",
        "tpaaP11RecommendationLane",
    ):
        assert root.findChild(QtWidgets.QGroupBox, lane) is not None
    assert not root.findChild(QtWidgets.QPushButton, "tpaaP11ExternalPluginInstall").isEnabled()
    assert not root.findChild(QtWidgets.QPushButton, "tpaaP11ModelRollback").isEnabled()
    assert not root.findChild(QtWidgets.QPushButton, "tpaaP11MediaExport").isEnabled()
    root.close()
    app.processEvents()
