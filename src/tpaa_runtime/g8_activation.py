"""Atomic, read-only G8 runtime activation pre-publication gate."""

from __future__ import annotations

from dataclasses import dataclass

from tpaa_application import ApplicationService
from tpaa_security import route_security

from .gui_capabilities import GuiCapabilitySet


class G8ActivationError(RuntimeError):
    """No partially constructed G8 runtime may be published."""


@dataclass(frozen=True, slots=True)
class G8ActivationReceipt:
    core_baseline: str
    routes: tuple[str, ...]
    capability_state: str


_ROUTES = (
    ("api.route.102", "/api/v1/gui/attack-clusters/probe/co-attack-analysis"),
)


def validate_g8_activation(
    capabilities: GuiCapabilitySet,
    application: ApplicationService,
) -> G8ActivationReceipt | None:
    """Validate every G8 activation dependency before returning a public runtime."""

    if "G8" not in capabilities.active:
        return None
    if not application.has_co_attack():
        raise G8ActivationError("G8_ACTIVATION_COMPONENT_MISMATCH")
    state = application.co_attack().capability_state()
    if state != "READY":
        raise G8ActivationError(f"G8_ACTIVATION_ADAPTER_NOT_READY:{state}")
    route_ids: list[str] = []
    for expected, path in _ROUTES:
        binding = route_security("GET", path)
        if binding is None or binding.route_id != expected:
            raise G8ActivationError(f"G8_ACTIVATION_ROUTE_MISMATCH:{expected}")
        route_ids.append(binding.route_id)
    return G8ActivationReceipt(
        core_baseline=capabilities.core_baseline,
        routes=tuple(route_ids),
        capability_state=state,
    )


__all__ = ["G8ActivationError", "G8ActivationReceipt", "validate_g8_activation"]
