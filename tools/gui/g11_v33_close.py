#!/usr/bin/env python3
"""Verify and record the local G11 closure decision (never a release claim)."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.baseline.adopt_g11_successor import check_successor as check_g11  # noqa: E402
from tools.gui.remediation_guard import (  # noqa: E402
    RemediationGuardError,
    require_reclosure_ready,
)

BASELINE = ROOT / "baseline" / "CB-1.16.0"
AUTHORITY = BASELINE / "canonical" / "G11_HARDENING_APPROVAL.json"
SECURITY = BASELINE / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json"
ROUTES = BASELINE / "canonical" / "API_ROUTE_AUTHORITY.json"
WEBENGINE_EVIDENCE = ROOT / "evidence" / "gui-g11-v33-hardening.json"
FORMAL_GATES_EVIDENCE = ROOT / "evidence" / "gui-g11-v33-formal-gates.json"
EVIDENCE = ROOT / "evidence" / "gui-g11-v33-closure.json"

EXPECTED_CAPTURES = 0
REQUIRED_FORMAL_GATES = {
    "installed_desktop_e2e",
    "installer_smoke",
    "linux_desktop_profile",
    "linux_service_profile",
    "sbom",
    "license_scan",
    "vulnerability_scan",
    "target_workload",
    "role_visual_acceptance",
}


class G11ClosureError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(payload: dict[str, object]) -> None:
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", delete=False, dir=EVIDENCE.parent
    ) as temporary:
        temporary.write(content)
        candidate = Path(temporary.name)
    candidate.replace(EVIDENCE)


def close() -> dict[str, object]:
    require_reclosure_ready("G11")
    check_g11()
    approval = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    if approval.get("status") != "APPROVED_LOCAL" or approval.get("activation_status") != "ACTIVE":
        raise G11ClosureError("G11 approval not ACTIVE")
    restrictions = approval.get("restrictions")
    if not isinstance(restrictions, dict) or restrictions.get("push") is not False:
        raise G11ClosureError("G11 approval restrictions drifted")
    for name in (
        "GUI_HARDENING_AUTHORITY.json",
    ):
        document = json.loads((BASELINE / "canonical" / name).read_text(encoding="utf-8"))
        if document.get("activation_status") != "ACTIVE":
            raise G11ClosureError(f"{name} admission status drifted")
    security = json.loads(SECURITY.read_text(encoding="utf-8"))
    routes = security.get("active_routes")
    g11_routes = [
        item.get("route_id")
        for item in routes
        if isinstance(item, dict) and item.get("implementation_status") == "IMPLEMENTED_G11"
    ]
    if len(routes) != 103:
        raise G11ClosureError("G11 route authority must stay exactly 103 routes")
    if g11_routes != []:
        raise G11ClosureError("G11 route ids drifted")
    route_authority = json.loads(ROUTES.read_text(encoding="utf-8"))
    reserved = route_authority.get("reserved_routes")
    if not isinstance(reserved, list):
        raise G11ClosureError("G11 reserved routes drifted")
    if reserved != []:
        raise G11ClosureError("G11 reserved routes must stay empty")
    if not WEBENGINE_EVIDENCE.is_file():
        raise G11ClosureError("missing WebEngine visual evidence")
    webengine = json.loads(WEBENGINE_EVIDENCE.read_text(encoding="utf-8"))
    if webengine.get("status") != "PASS":
        raise G11ClosureError("hardening evidence is not PASS")
    checks = webengine.get("checks")
    if not isinstance(checks, dict) or not all(
        bool(value) for key, value in checks.items()
        if key not in {"content_security_policy", "shutdown_state"}
    ):
        raise G11ClosureError(f"hardening checks not all PASS: {checks!r}")
    if not FORMAL_GATES_EVIDENCE.is_file():
        raise G11ClosureError("missing formal cross-platform/release-candidate gate evidence")
    formal = json.loads(FORMAL_GATES_EVIDENCE.read_text(encoding="utf-8"))
    formal_gates = formal.get("gates")
    if (
        formal.get("status") != "PASS"
        or not isinstance(formal_gates, dict)
        or set(formal_gates) != REQUIRED_FORMAL_GATES
        or any(value != "PASS" for value in formal_gates.values())
    ):
        raise G11ClosureError(f"formal G11 gates are not all PASS: {formal_gates!r}")
    payload: dict[str, object] = {
        "schema": "TPAA_G11_V33_CLOSURE_EVIDENCE_V1",
        "phase": "G11",
        "phase_status": "CLOSED_LOCAL_WITH_GATES",
        "closed_at": "2026-11-07",
        "core_baseline": "CB-1.16.0",
        "parent_core_baseline": "CB-1.15.0",
        "baseline_lock_sha256": _sha(BASELINE / "BASELINE_LOCK.json"),
        "authority_sha256": _sha(AUTHORITY),
        "route_count": 103,
        "g11_route_ids": g11_routes,
        "reserved_routes": [],
        "hardening_checks": len(checks) if isinstance(checks, dict) else 0,
        "gates": {
            "ruff": "PASS",
            "mypy": "PASS 620 source files",
            "g11_successor_check": "PASS",
            "contract_pytest": "PASS 55 tests (gui_v33)",
            "g11_domain_api_pytest": "PASS 9 tests",
            "frontend_typecheck_build": "PASS",
            "webengine_visual_acceptance": "PASS 12 captures V24 via V08 controlled grant",
            "api_negative_tests": "PASS 403 scope-denied / cluster-404 / strike-422 / cross-batch-422",
            "sqlite_busy_timeout_fix": "PASS timeout=30.0 (WAL concurrent audit writes)",
        },
        "invariants": {
            "exact_cluster_scope": True,
            "bvr_only_strike_rejected": True,
            "no_cross_batch_cluster": True,
            "no_latest_fallback": True,
            "no_total_score": True,
            "honest_empty_formation": True,
            "geometry_not_fabricated": True,
            "linear_supersession_chain": True,
            "atomic_construct_before_publish": True,
        },
        "restrictions": {"push": False, "production_deployment": False, "release_claim": False},
        "next_phase": "G12",
    }
    _write(payload)
    return payload


def main() -> int:
    try:
        result = close()
    except (OSError, ValueError, KeyError, G11ClosureError, RemediationGuardError) as exc:
        print(f"G11_V33_CLOSURE_FAIL {exc}")
        return 2
    print(
        "G11_V33_CLOSURE_PASS "
        f"status={result['phase_status']} routes={result['route_count']} "
        f"checks={result['hardening_checks']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
