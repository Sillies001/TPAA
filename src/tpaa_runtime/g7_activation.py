"""Atomic, read-only G7 runtime activation pre-publication gate."""

from __future__ import annotations

from dataclasses import dataclass

from tpaa_application import ApplicationService
from tpaa_security import route_security

from .gui_capabilities import GuiCapabilitySet


class G7ActivationError(RuntimeError):
    """No partially constructed G7 runtime may be published."""


@dataclass(frozen=True, slots=True)
class G7ActivationReceipt:
    core_baseline: str
    routes: tuple[str, ...]
    capability_state: str


_ROUTES = (
    ("api.route.101", "/api/v1/gui/batches/b-probe/weapon-events"),
)


def validate_g7_activation(
    capabilities: GuiCapabilitySet,
    application: ApplicationService,
) -> G7ActivationReceipt | None:
    """Validate every G7 activation dependency before returning a public runtime."""

    if "G7" not in capabilities.active:
        return None
    if not application.has_batch_events():
        raise G7ActivationError("G7_ACTIVATION_COMPONENT_MISMATCH")
    state = application.batch_events().capability_state()
    if state != "READY":
        raise G7ActivationError(f"G7_ACTIVATION_ADAPTER_NOT_READY:{state}")
    route_ids: list[str] = []
    for expected, path in _ROUTES:
        binding = route_security("GET", path)
        if binding is None or binding.route_id != expected:
            raise G7ActivationError(f"G7_ACTIVATION_ROUTE_MISMATCH:{expected}")
        route_ids.append(binding.route_id)
    return G7ActivationReceipt(
        core_baseline=capabilities.core_baseline,
        routes=tuple(route_ids),
        capability_state=state,
    )


__all__ = ["G7ActivationError", "G7ActivationReceipt", "validate_g7_activation"]
