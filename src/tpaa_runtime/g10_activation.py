"""Atomic, read-only G10 runtime activation pre-publication gate."""

from __future__ import annotations

from dataclasses import dataclass

from tpaa_application import ApplicationService
from tpaa_security import route_security

from .gui_capabilities import GuiCapabilitySet


class G10ActivationError(RuntimeError):
    """No partially constructed G10 runtime may be published."""


@dataclass(frozen=True, slots=True)
class G10ActivationReceipt:
    core_baseline: str
    routes: tuple[str, ...]
    capability_state: str


# G10 closes the remaining views without adding security routes: the route authority
# must remain exactly the G9 graph (103 routes, nothing reserved).
_ROUTES = (
    ("api.route.101", "/api/v1/gui/batches/probe/weapon-events"),
    ("api.route.102", "/api/v1/gui/attack-clusters/probe/co-attack-analysis"),
    ("api.route.103", "/api/v1/gui/weapon-events/probe/replay-context"),
)


def validate_g10_activation(
    capabilities: GuiCapabilitySet,
    application: ApplicationService,
) -> G10ActivationReceipt | None:
    """Validate every G10 activation dependency before returning a public runtime."""

    if "G10" not in capabilities.active:
        return None
    route_ids: list[str] = []
    for expected, path in _ROUTES:
        binding = route_security("GET", path)
        if binding is None or binding.route_id != expected:
            raise G10ActivationError(f"G10_ACTIVATION_ROUTE_MISMATCH:{expected}")
        route_ids.append(binding.route_id)
    return G10ActivationReceipt(
        core_baseline=capabilities.core_baseline,
        routes=tuple(route_ids),
        capability_state="READY",
    )


__all__ = ["G10ActivationError", "G10ActivationReceipt", "validate_g10_activation"]
