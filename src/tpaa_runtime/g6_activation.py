"""Atomic, read-only G6 runtime activation pre-publication gate."""

from __future__ import annotations

from dataclasses import dataclass

from tpaa_application import ApplicationService
from tpaa_security import route_security

from .gui_capabilities import GuiCapabilitySet


class G6ActivationError(RuntimeError):
    """No partially constructed G6 runtime may be published."""


@dataclass(frozen=True, slots=True)
class G6ActivationReceipt:
    core_baseline: str
    routes: tuple[str, ...]
    capability_state: str


_ROUTES = (
    ("api.route.100", "/api/v1/gui/historical-overview"),
)

def validate_g6_activation(
    capabilities: GuiCapabilitySet,
    application: ApplicationService,
) -> G6ActivationReceipt | None:
    """Validate every G6 activation dependency before returning a public runtime."""

    if "G6" not in capabilities.active:
        return None
    if not application.has_historical_overview():
        raise G6ActivationError("G6_ACTIVATION_COMPONENT_MISMATCH")
    state = application.historical_overview().capability_state()
    if state != "READY":
        raise G6ActivationError(f"G6_ACTIVATION_ADAPTER_NOT_READY:{state}")
    route_ids: list[str] = []
    for expected, path in _ROUTES:
        binding = route_security("GET", path)
        if binding is None or binding.route_id != expected:
            raise G6ActivationError(f"G6_ACTIVATION_ROUTE_MISMATCH:{expected}")
        route_ids.append(binding.route_id)
    return G6ActivationReceipt(
        core_baseline=capabilities.core_baseline,
        routes=tuple(route_ids),
        capability_state=state,
    )


__all__ = ["G6ActivationError", "G6ActivationReceipt", "validate_g6_activation"]
