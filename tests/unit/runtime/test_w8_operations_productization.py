from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tpaa_api.runtime import register_product_runtime_routes
from tpaa_application import ApplicationService
from tpaa_qualification import load_m5_qualification_authority
from tpaa_runtime import (
    W8_EVIDENCE_CATEGORIES,
    W8_TARGET_PROFILES,
    ProductionRuntimeConfig,
    RuntimeProfile,
    W8ControlReceipt,
    W8OperationsError,
    W8OperationsStatus,
    W8ServiceRecoveryOrchestrator,
    W8TargetProfileEvidence,
    build_desktop_production_runtime,
    build_w8_operations_status,
)
from tpaa_storage import bootstrap_sqlite

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "baseline" / "CB-1.5.0"
SNAPSHOT = "a" * 64


class _UnusedStorage:
    def execute(self) -> Any:
        raise AssertionError("storage is outside the W8 status read")


class _ServiceControl:
    def __init__(self, *, health_state: str = "READY") -> None:
        self.health_state = health_state
        self.calls: list[str] = []

    def _receipt(self, stage: str, state: str) -> W8ControlReceipt:
        self.calls.append(stage)
        return W8ControlReceipt(stage, state, SNAPSHOT, f"op:{stage.lower()}")

    def write_drain(self) -> W8ControlReceipt:
        return self._receipt("WRITE_DRAIN", "MANAGED_WRITES_BLOCKED")

    def snapshot(self, drain: W8ControlReceipt) -> W8ControlReceipt:
        assert drain.stage == "WRITE_DRAIN"
        return self._receipt("SNAPSHOT", "VERIFIED")

    def restore_staging(self, snapshot: W8ControlReceipt) -> W8ControlReceipt:
        assert snapshot.state == "VERIFIED"
        return self._receipt("RESTORE_STAGING", "VERIFIED_NOT_ACTIVATED")

    def activate(self, restored: W8ControlReceipt) -> W8ControlReceipt:
        assert restored.state == "VERIFIED_NOT_ACTIVATED"
        return self._receipt("ACTIVATE", "ACTIVATED_PENDING_HEALTH")

    def health_check(self, activated: W8ControlReceipt) -> W8ControlReceipt:
        assert activated.state == "ACTIVATED_PENDING_HEALTH"
        return self._receipt("HEALTH_CHECK", self.health_state)

    def rollback(self, activated: W8ControlReceipt) -> W8ControlReceipt:
        assert activated.state == "ACTIVATED_PENDING_HEALTH"
        return self._receipt("ROLLBACK", "PRIOR_TARGET_RESTORED")


def _accepted_profiles() -> tuple[W8TargetProfileEvidence, ...]:
    return tuple(
        W8TargetProfileEvidence(
            profile_id=profile,
            state="ACCEPTED",
            endpoint_ref=f"target://qualification/{profile.lower()}",
            evidence_sha256=str(index + 1) * 64,
            categories={category: "PASS" for category in W8_EVIDENCE_CATEGORIES},
        )
        for index, profile in enumerate(W8_TARGET_PROFILES)
    )


def test_w8_local_closure_freezes_authority_and_keeps_targets_closed() -> None:
    status = W8OperationsStatus.local_closed(
        load_m5_qualification_authority(BASELINE)
    ).execute()

    assert status["schema"] == "TPAA_W8_OPERATIONS_STATUS_V1"
    assert status["workload_envelope"] == {
        "state": "FROZEN",
        "workload_id": "M5_P1_QUALIFICATION_WORKLOAD_V1",
        "workload_version": "1.0.0",
        "session_count": 50,
        "total_observation_target": 5800,
        "api_query_count": 1000,
        "desktop_concurrency": 2,
        "service_concurrency": 8,
    }
    assert status["recovery_objectives"] == {
        "committed_published_release_rpo_seconds": 0,
        "restore_rto_seconds_max": 1800,
        "partial_cross_store_restore_permitted": False,
    }
    assert status["production_activation_allowed"] is False
    assert status["target_environment_acceptance_claimed"] is False
    assert all(
        item["state"] == "LOCAL_VERIFIED_TARGET_PENDING"
        for item in status["target_profiles"]
    )


def test_w8_target_acceptance_requires_complete_hash_bound_evidence() -> None:
    authority = load_m5_qualification_authority(BASELINE)
    accepted = W8OperationsStatus(authority, _accepted_profiles()).execute()
    assert accepted["production_activation_allowed"] is True
    assert accepted["target_environment_acceptance_claimed"] is True

    with pytest.raises(W8OperationsError, match="SHA256_INVALID"):
        W8TargetProfileEvidence(
            profile_id=W8_TARGET_PROFILES[0],
            state="ACCEPTED",
            endpoint_ref="target://qualification/windows-desktop",
            evidence_sha256="not-a-hash",
            categories={category: "PASS" for category in W8_EVIDENCE_CATEGORIES},
        )

    records = [item.projection() for item in _accepted_profiles()]
    configured = build_w8_operations_status(authority, records).execute()
    assert configured["production_activation_allowed"] is True

    with pytest.raises(TypeError):
        _accepted_profiles()[0].categories[W8_EVIDENCE_CATEGORIES[0]] = "PENDING"


def test_w8_service_control_orders_activation_after_verified_staging() -> None:
    control = _ServiceControl()
    audits: list[dict[str, object]] = []
    result = W8ServiceRecoveryOrchestrator(control, audit=audits.append).execute()

    assert control.calls == [
        "WRITE_DRAIN",
        "SNAPSHOT",
        "RESTORE_STAGING",
        "ACTIVATE",
        "HEALTH_CHECK",
    ]
    assert result["state"] == "ACTIVATED_READY"
    assert result["snapshot_sha256"] == SNAPSHOT
    assert len(audits) == 5
    assert all(item["snapshot_sha256"] == SNAPSHOT for item in audits)


def test_w8_service_control_rolls_back_failed_activation_health() -> None:
    control = _ServiceControl(health_state="DEGRADED")

    with pytest.raises(
        W8OperationsError,
        match="W8_ACTIVATION_HEALTH_FAILED_ROLLED_BACK",
    ):
        W8ServiceRecoveryOrchestrator(control).execute()

    assert control.calls[-2:] == ["HEALTH_CHECK", "ROLLBACK"]


def test_w8_runtime_status_is_machine_readable_and_missing_status_fails_closed() -> None:
    configured = ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),
        w8_operations_status=W8OperationsStatus.local_closed(
            load_m5_qualification_authority(BASELINE)
        ),
    )
    configured_client = TestClient(
        register_product_runtime_routes(FastAPI(), configured)
    )
    response = configured_client.get("/runtime/operations")
    assert response.status_code == 200
    assert response.json()["production_activation_allowed"] is False

    missing = ApplicationService(get_storage_baseline_status=_UnusedStorage())
    missing_client = TestClient(register_product_runtime_routes(FastAPI(), missing))
    unavailable = missing_client.get("/runtime/operations")
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == (
        "W8_OPERATIONS_STATUS_NOT_CONFIGURED"
    )


def test_w8_status_is_wired_into_production_composition(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.sqlite3"
    bootstrap_sqlite(database)
    runtime = build_desktop_production_runtime(
        ProductionRuntimeConfig(
            profile=RuntimeProfile.DESKTOP,
            product_build_version="1.0.1",
            authority_root=BASELINE / "canonical",
            object_root=tmp_path / "objects",
            desktop_database_path=database,
        )
    )

    status = runtime.application.w8_operations_status()
    assert status["production_activation_allowed"] is False
    assert status["authority"]["baseline_lock_sha256"] == (
        "ecdb68d0aa17ad49b2b0b3bdbad0e82559cd455725a0eb2a2a4855feba99edab"
    )
