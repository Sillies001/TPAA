"""Atomic, read-only G11 runtime activation pre-publication gate."""

from __future__ import annotations

from dataclasses import dataclass

from tpaa_application import ApplicationService
from tpaa_security import route_security

from .gui_capabilities import GuiCapabilitySet


class G11ActivationError(RuntimeError):
    """No partially constructed G11 runtime may be published."""


@dataclass(frozen=True, slots=True)
class G11ActivationReceipt:
    core_baseline: str
    routes: tuple[str, ...]
    capability_state: str


_ROUTES = (
    ("api.route.101", "/api/v1/gui/batches/probe/weapon-events"),
    ("api.route.102", "/api/v1/gui/attack-clusters/probe/co-attack-analysis"),
    ("api.route.103", "/api/v1/gui/weapon-events/probe/replay-context"),
)


def validate_g11_activation(
    capabilities: GuiCapabilitySet,
    application: ApplicationService,
) -> G11ActivationReceipt | None:
    """Validate every G11 activation dependency before returning a public runtime."""

    if "G11" not in capabilities.active:
        return None
    route_ids: list[str] = []
    for expected, path in _ROUTES:
        binding = route_security("GET", path)
        if binding is None or binding.route_id != expected:
            raise G11ActivationError(f"G11_ACTIVATION_ROUTE_MISMATCH:{expected}")
        route_ids.append(binding.route_id)
    return G11ActivationReceipt(
        core_baseline=capabilities.core_baseline,
        routes=tuple(route_ids),
        capability_state="READY",
    )


__all__ = ["G11ActivationError", "G11ActivationReceipt", "validate_g11_activation"]
