"""Trusted, lock-pinned GUI phase capability resolver.

Directory names never activate a phase.  Activation requires an exact trusted
``BASELINE_LOCK`` plus a controlled, locally approved and active phase decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tpaa_canonical import CanonicalArtifactError, trusted_loader_for_baseline


class GuiCapabilityError(RuntimeError):
    """Fail-closed GUI capability admission error."""


@dataclass(frozen=True, slots=True)
class GuiCapabilitySet:
    core_baseline: str
    active: frozenset[str]
    approval_ids: tuple[str, ...]

    def requires(self, capability: str) -> None:
        if capability not in self.active:
            raise GuiCapabilityError(f"GUI_CAPABILITY_NOT_ACTIVE:{capability}")


_PHASE_APPROVALS = (
    ("G2", "G2_GUI_SECURITY_APPROVAL"),
    ("G3", "G3_GATEWAY_APPROVAL"),
    ("G4", "G4_BATCH_IMPORT_APPROVAL"),
    ("G5", "G5_WEAPON_EVENT_APPROVAL"),
    ("G6", "G6_HISTORICAL_OVERVIEW_APPROVAL"),
    ("G7", "G7_BATCH_EVENTS_APPROVAL"),
    ("G8", "G8_CO_ATTACK_APPROVAL"),
    ("G9", "G9_REPLAY_APPROVAL"),
    ("G10", "G10_VIEW_CLOSURE_APPROVAL"),
    ("G11", "G11_HARDENING_APPROVAL"),
    ("G12", "G12_DESIGN_FREEZE_APPROVAL"),
)


def _validate_contiguous_phase_lineage(active: set[str]) -> None:
    """Reject a successor approval if any required predecessor is absent.

    The exact baseline lock proves artifact integrity.  This additional check
    proves semantic lineage, so individual activation modules do not need an
    ever-growing tuple of accepted baseline directory names.
    """

    seen_gap = False
    for phase, _artifact_id in _PHASE_APPROVALS:
        if phase not in active:
            seen_gap = True
            continue
        if seen_gap:
            raise GuiCapabilityError(f"GUI_PHASE_LINEAGE_GAP:{phase}")


def resolve_gui_capabilities(authority_root: Path) -> GuiCapabilitySet:
    """Resolve active phases only from a pinned baseline and controlled approvals."""

    baseline_root = authority_root.resolve().parent
    try:
        loader = trusted_loader_for_baseline(baseline_root)
    except CanonicalArtifactError as exc:
        raise GuiCapabilityError(f"GUI_BASELINE_UNTRUSTED:{exc.reason}") from exc
    active: set[str] = set()
    approvals: list[str] = []
    for phase, artifact_id in _PHASE_APPROVALS:
        if artifact_id not in loader.artifact_ids:
            continue
        try:
            payload = loader.load(artifact_id).payload
        except CanonicalArtifactError as exc:
            raise GuiCapabilityError(f"GUI_APPROVAL_UNTRUSTED:{artifact_id}:{exc.reason}") from exc
        restrictions = payload.get("restrictions")
        if not isinstance(restrictions, dict):
            raise GuiCapabilityError(f"GUI_APPROVAL_RESTRICTIONS_INVALID:{artifact_id}")
        if (
            payload.get("status") != "APPROVED_LOCAL"
            or payload.get("activation_status") != "ACTIVE"
            or restrictions.get("push") is not False
            or restrictions.get("production_deployment") is not False
            or restrictions.get("release_claim") is not False
        ):
            raise GuiCapabilityError(f"GUI_APPROVAL_NOT_ACTIVE:{artifact_id}")
        approval_id = payload.get("approval_id")
        if not isinstance(approval_id, str) or not approval_id:
            raise GuiCapabilityError(f"GUI_APPROVAL_ID_INVALID:{artifact_id}")
        active.add(phase)
        approvals.append(approval_id)
    _validate_contiguous_phase_lineage(active)
    return GuiCapabilitySet(
        core_baseline=loader.expected_core_baseline,
        active=frozenset(active),
        approval_ids=tuple(approvals),
    )


__all__ = [
    "GuiCapabilityError",
    "GuiCapabilitySet",
    "resolve_gui_capabilities",
]
