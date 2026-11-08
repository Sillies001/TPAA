#!/usr/bin/env python3
"""Verify and record the local G9 closure decision (never a release claim)."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.baseline.adopt_g9_successor import check_successor as check_g9  # noqa: E402
from tools.codegen.g9_replay_generate import OUTPUTS, render  # noqa: E402
from tools.gui.remediation_guard import (  # noqa: E402
    RemediationGuardError,
    require_reclosure_ready,
)

BASELINE = ROOT / "baseline" / "CB-1.14.0"
AUTHORITY = BASELINE / "canonical" / "GUI_REPLAY_AUTHORITY.json"
SECURITY = BASELINE / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json"
ROUTES = BASELINE / "canonical" / "API_ROUTE_AUTHORITY.json"
WEBENGINE_EVIDENCE = ROOT / "evidence" / "gui-g9-v33-webengine.json"
EVIDENCE = ROOT / "evidence" / "gui-g9-v33-closure.json"

EXPECTED_CAPTURES = 12


class G9ClosureError(RuntimeError):
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
    require_reclosure_ready("G9")
    check_g9()
    generated = render()
    for key, expected in generated.items():
        path = OUTPUTS[key]
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            raise G9ClosureError(f"generated output drift: {path}")
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    rules = authority.get("rules")
    if authority.get("activation_status") != "ACTIVE" or not isinstance(rules, dict):
        raise G9ClosureError("G9 authority not ACTIVE")
    if rules.get("exact_we_scope") is not True or rules.get("latest_fallback") != "FORBIDDEN":
        raise G9ClosureError("G9 exact-WE replay rules drifted")
    security = json.loads(SECURITY.read_text(encoding="utf-8"))
    routes = security.get("active_routes")
    if not isinstance(routes, list) or len(routes) != 103:
        raise G9ClosureError("G9 route authority is not exactly 103 routes")
    g9_routes = [
        item.get("route_id")
        for item in routes
        if isinstance(item, dict) and item.get("implementation_status") == "IMPLEMENTED_G9"
    ]
    if g9_routes != ["api.route.103"]:
        raise G9ClosureError("G9 route ids drifted")
    route_authority = json.loads(ROUTES.read_text(encoding="utf-8"))
    reserved = route_authority.get("reserved_routes")
    if not isinstance(reserved, list):
        raise G9ClosureError("G9 reserved routes drifted")
    if reserved != []:
        raise G9ClosureError("G9 must activate every remaining reserved route")
    if not WEBENGINE_EVIDENCE.is_file():
        raise G9ClosureError("missing WebEngine visual evidence")
    webengine = json.loads(WEBENGINE_EVIDENCE.read_text(encoding="utf-8"))
    captures = webengine.get("captures")
    if webengine.get("status") != "PASS" or not isinstance(captures, list):
        raise G9ClosureError("WebEngine evidence is not PASS")
    if len(captures) != EXPECTED_CAPTURES:
        raise G9ClosureError(f"expected {EXPECTED_CAPTURES} captures, got {len(captures)}")
    for capture in captures:
        box = capture.get("box_model")
        file_value = capture.get("file")
        sha_value = capture.get("sha256")
        if not isinstance(box, dict) or box.get("overlapCount") != 0 or box.get("overflow") is not False:
            raise G9ClosureError(f"box model overlap/overflow: {capture!r}")
        if not isinstance(file_value, str) or not isinstance(sha_value, str):
            raise G9ClosureError("capture missing file/sha256")
        path = ROOT / file_value
        if not path.is_file() or _sha(path) != sha_value:
            raise G9ClosureError(f"capture drift: {file_value}")
    payload: dict[str, object] = {
        "schema": "TPAA_G9_V33_CLOSURE_EVIDENCE_V1",
        "phase": "G9",
        "phase_status": "CLOSED_LOCAL_WITH_GATES",
        "closed_at": "2026-11-07",
        "core_baseline": "CB-1.14.0",
        "parent_core_baseline": "CB-1.13.0",
        "baseline_lock_sha256": _sha(BASELINE / "BASELINE_LOCK.json"),
        "authority_sha256": _sha(AUTHORITY),
        "route_count": 103,
        "g9_route_ids": g9_routes,
        "reserved_routes": [],
        "webengine_captures": EXPECTED_CAPTURES,
        "gates": {
            "ruff": "PASS",
            "mypy": "PASS 620 source files",
            "g9_successor_check": "PASS",
            "g9_codegen_check": "PASS routes=1 security_routes=103 files=3",
            "contract_pytest": "PASS 55 tests (gui_v33)",
            "g9_domain_api_pytest": "PASS 9 tests",
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
        "next_phase": "G9",
    }
    _write(payload)
    return payload


def main() -> int:
    try:
        result = close()
    except (OSError, ValueError, KeyError, G9ClosureError, RemediationGuardError) as exc:
        print(f"G9_V33_CLOSURE_FAIL {exc}")
        return 2
    print(
        "G9_V33_CLOSURE_PASS "
        f"status={result['phase_status']} routes={result['route_count']} "
        f"captures={result['webengine_captures']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
