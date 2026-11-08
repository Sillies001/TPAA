"""Atomic, read-only G5 runtime activation pre-publication gate."""

from __future__ import annotations

from dataclasses import dataclass

from tpaa_application import ApplicationService
from tpaa_security import route_security

from .gui_capabilities import GuiCapabilitySet


class G5ActivationError(RuntimeError):
    """No partially constructed G5 runtime may be published."""


@dataclass(frozen=True, slots=True)
class G5ActivationReceipt:
    core_baseline: str
    routes: tuple[str, ...]
    capability_state: str


_ROUTES = (
    ("api.route.097", "/api/v1/gui/weapon-events/probe"),
    ("api.route.098", "/api/v1/gui/weapon-events/probe/windows/shooter"),
    ("api.route.099", "/api/v1/gui/weapon-events/probe/perspectives/shooter"),
)

def validate_g5_activation(
    capabilities: GuiCapabilitySet,
    application: ApplicationService,
) -> G5ActivationReceipt | None:
    """Validate every activation dependency before returning a public runtime."""

    if "G5" not in capabilities.active:
        return None
    if not application.has_weapon_event():
        raise G5ActivationError("G5_ACTIVATION_COMPONENT_MISMATCH")
    state = application.weapon_event().capability_state()
    if state != "READY":
        raise G5ActivationError(f"G5_ACTIVATION_ADAPTER_NOT_READY:{state}")
    route_ids: list[str] = []
    for expected, path in _ROUTES:
        binding = route_security("GET", path)
        if binding is None or binding.route_id != expected:
            raise G5ActivationError(f"G5_ACTIVATION_ROUTE_MISMATCH:{expected}")
        route_ids.append(binding.route_id)
    return G5ActivationReceipt(
        core_baseline=capabilities.core_baseline,
        routes=tuple(route_ids),
        capability_state=state,
    )


__all__ = ["G5ActivationError", "G5ActivationReceipt", "validate_g5_activation"]
