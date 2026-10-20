from __future__ import annotations

import json
from pathlib import Path

import pytest

from tpaa_runtime import (
    AtomicFileServiceTrafficSwitch,
    ServiceActivationError,
    ServiceStagingGeneration,
    activate_verified_service_staging,
)

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64
_DIGEST_C = "c" * 64
_DIGEST_D = "d" * 64


def _receipt(snapshot: str = _DIGEST_B) -> dict[str, object]:
    return {
        "schema": "TPAA_SERVICE_STAGING_RESTORE_V1",
        "profile": "SERVICE",
        "database_state": "VERIFIED_STAGING",
        "object_state": "VERIFIED_STAGING",
        "activation_state": "NOT_ACTIVATED",
        "activation_required": True,
        "snapshot_sha256": snapshot,
    }


def _target() -> ServiceStagingGeneration:
    return ServiceStagingGeneration(
        generation_id="green-20261013",
        application_build_sha256=_DIGEST_A,
        snapshot_sha256=_DIGEST_B,
        database_identity_sha256=_DIGEST_C,
        object_store_identity_sha256=_DIGEST_D,
    )


class FakeTrafficSwitch:
    def __init__(self, *, healthy: bool = True) -> None:
        self.active = "blue-20261012"
        self.healthy = healthy
        self.events: list[tuple[object, ...]] = []

    def current_generation(self) -> str:
        self.events.append(("current", self.active))
        return self.active

    def set_write_enabled(self, generation_id: str, *, enabled: bool) -> None:
        self.events.append(("write", generation_id, enabled))

    def route_to(self, generation_id: str) -> None:
        self.events.append(("route", generation_id))
        self.active = generation_id

    def health_check(self, generation_id: str) -> bool:
        self.events.append(("health", generation_id))
        return self.healthy


def test_verified_staging_routes_read_disabled_then_opens_writes() -> None:
    switch = FakeTrafficSwitch()
    result = activate_verified_service_staging(
        restore_receipt=_receipt(),
        target=_target(),
        traffic_switch=switch,
    )
    assert result.state == "ACTIVE"
    assert result.previous_generation_id == "blue-20261012"
    assert result.active_generation_id == "green-20261013"
    assert result.writes_enabled is True
    assert switch.events == [
        ("current", "blue-20261012"),
        ("write", "green-20261013", False),
        ("route", "green-20261013"),
        ("health", "green-20261013"),
        ("write", "green-20261013", True),
    ]


def test_unhealthy_staging_rolls_back_before_any_write_enable() -> None:
    switch = FakeTrafficSwitch(healthy=False)
    with pytest.raises(ServiceActivationError, match="health check failed"):
        activate_verified_service_staging(
            restore_receipt=_receipt(),
            target=_target(),
            traffic_switch=switch,
        )
    assert switch.active == "blue-20261012"
    assert ("write", "green-20261013", True) not in switch.events
    assert switch.events[-1] == ("route", "blue-20261012")


def test_snapshot_mismatch_fails_before_control_plane_change() -> None:
    switch = FakeTrafficSwitch()
    with pytest.raises(ServiceActivationError, match="snapshot does not match"):
        activate_verified_service_staging(
            restore_receipt=_receipt(_DIGEST_C),
            target=_target(),
            traffic_switch=switch,
        )
    assert switch.events == []


def test_atomic_file_switch_persists_only_generation_identity(tmp_path: Path) -> None:
    state = tmp_path / "active-generation.json"
    writes: list[tuple[str, bool]] = []
    switch = AtomicFileServiceTrafficSwitch(
        state,
        health_probe=lambda generation: generation == "green-20261013",
        write_control=lambda generation, enabled: writes.append((generation, enabled)),
    )
    switch.route_to("blue-20261012")
    result = activate_verified_service_staging(
        restore_receipt=_receipt(),
        target=_target(),
        traffic_switch=switch,
    )
    persisted = json.loads(state.read_text(encoding="utf-8"))
    assert persisted["generation_id"] == "green-20261013"
    assert set(persisted) == {"schema", "generation_id", "updated_at_utc"}
    assert writes == [("green-20261013", False), ("green-20261013", True)]
    assert result.health_verified is True
