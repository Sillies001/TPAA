"""Atomic, read-only G9 runtime activation pre-publication gate."""

from __future__ import annotations

from dataclasses import dataclass

from tpaa_application import ApplicationService
from tpaa_security import route_security

from .gui_capabilities import GuiCapabilitySet


class G9ActivationError(RuntimeError):
    """No partially constructed G9 runtime may be published."""


@dataclass(frozen=True, slots=True)
class G9ActivationReceipt:
    core_baseline: str
    routes: tuple[str, ...]
    capability_state: str


_ROUTES = (
    ("api.route.103", "/api/v1/gui/weapon-events/probe/replay-context"),
)


def validate_g9_activation(
    capabilities: GuiCapabilitySet,
    application: ApplicationService,
) -> G9ActivationReceipt | None:
    """Validate every G9 activation dependency before returning a public runtime."""

    if "G9" not in capabilities.active:
        return None
    if not application.has_replay_context():
        raise G9ActivationError("G9_ACTIVATION_COMPONENT_MISMATCH")
    state = application.replay_context().capability_state()
    if state != "READY":
        raise G9ActivationError(f"G9_ACTIVATION_ADAPTER_NOT_READY:{state}")
    route_ids: list[str] = []
    for expected, path in _ROUTES:
        binding = route_security("GET", path)
        if binding is None or binding.route_id != expected:
            raise G9ActivationError(f"G9_ACTIVATION_ROUTE_MISMATCH:{expected}")
        route_ids.append(binding.route_id)
    return G9ActivationReceipt(
        core_baseline=capabilities.core_baseline,
        routes=tuple(route_ids),
        capability_state=state,
    )


__all__ = ["G9ActivationError", "G9ActivationReceipt", "validate_g9_activation"]
