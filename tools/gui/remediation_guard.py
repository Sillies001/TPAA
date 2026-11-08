"""Fail-closed guard for the G6-G12 post-closure remediation wave."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "evidence" / "gui-g6-g12-remediation-status.json"


class RemediationGuardError(RuntimeError):
    """A phase may not be reclosed before its remediation owner admits it."""


def require_reclosure_ready(phase: str) -> None:
    """Require an explicit, machine-readable readiness transition.

    This guard prevents legacy close scripts from overwriting truthful
    IN_PROGRESS evidence.  A phase owner may set READY_FOR_RECLOSURE only after
    every exit gate in the 2026-11-08 remediation plan has real evidence.
    """

    payload = json.loads(STATUS.read_text(encoding="utf-8"))
    stages = payload.get("stages")
    if not isinstance(stages, dict):
        raise RemediationGuardError("REMEDIATION_STATUS_INVALID")
    state = stages.get(phase)
    if state != "READY_FOR_RECLOSURE":
        raise RemediationGuardError(f"{phase}_RECLOSURE_BLOCKED:{state}")
    gate_files = payload.get("reclosure_gate_evidence")
    if not isinstance(gate_files, dict) or not isinstance(gate_files.get(phase), str):
        raise RemediationGuardError(f"{phase}_RECLOSURE_GATE_EVIDENCE_MISSING")
    gate_path = ROOT / str(gate_files[phase])
    gate_payload = json.loads(gate_path.read_text(encoding="utf-8"))
    gates = gate_payload.get("gates")
    if (
        gate_payload.get("stage") != phase
        or gate_payload.get("status") != "PASS"
        or not isinstance(gates, list)
        or not gates
        or any(not isinstance(gate, dict) or gate.get("exit_code") != 0 for gate in gates)
    ):
        raise RemediationGuardError(f"{phase}_RECLOSURE_GATE_EVIDENCE_INVALID")


__all__ = ["RemediationGuardError", "require_reclosure_ready"]
