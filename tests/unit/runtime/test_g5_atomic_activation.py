from __future__ import annotations

import pytest

from tpaa_application import ApplicationService, WeaponEventApplicationService
from tpaa_runtime.g5_activation import G5ActivationError, validate_g5_activation
from tpaa_runtime.gui_capabilities import GuiCapabilitySet


class _UnusedStorage:
    def execute(self) -> object:
        raise AssertionError


CAPABILITIES = GuiCapabilitySet(
    core_baseline="CB-1.10.0",
    active=frozenset({"G2", "G3", "G4", "G5"}),
    approval_ids=("g5",),
)

CAPABILITIES_G6_SUCCESSOR = GuiCapabilitySet(
    core_baseline="CB-1.11.0",
    active=frozenset({"G2", "G3", "G4", "G5", "G6"}),
    approval_ids=("g5", "g6"),
)


def test_g5_activation_validates_all_routes_before_publication() -> None:
    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),  # type: ignore[arg-type]
        weapon_event=WeaponEventApplicationService(),
    )
    receipt = validate_g5_activation(CAPABILITIES, application)
    assert receipt is not None
    assert receipt.routes == ("api.route.097", "api.route.098", "api.route.099")


def test_g5_activation_accepts_cb_1_11_0_successor_lineage() -> None:
    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),  # type: ignore[arg-type]
        weapon_event=WeaponEventApplicationService(),
    )
    receipt = validate_g5_activation(CAPABILITIES_G6_SUCCESSOR, application)
    assert receipt is not None
    assert receipt.core_baseline == "CB-1.11.0"
    assert receipt.routes == ("api.route.097", "api.route.098", "api.route.099")


def test_g5_activation_failure_returns_no_partial_receipt() -> None:
    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),  # type: ignore[arg-type]
    )
    with pytest.raises(G5ActivationError, match="COMPONENT_MISMATCH"):
        validate_g5_activation(CAPABILITIES, application)
