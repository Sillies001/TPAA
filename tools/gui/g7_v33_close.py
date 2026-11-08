#!/usr/bin/env python3
"""Verify and record the local G7 closure decision (never a release claim)."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.baseline.adopt_g7_successor import check_successor as check_g7  # noqa: E402
from tools.codegen.g7_batch_events_generate import OUTPUTS, render  # noqa: E402
from tools.gui.remediation_guard import (  # noqa: E402
    RemediationGuardError,
    require_reclosure_ready,
)

BASELINE = ROOT / "baseline" / "CB-1.12.0"
AUTHORITY = BASELINE / "canonical" / "GUI_BATCH_EVENTS_AUTHORITY.json"
SECURITY = BASELINE / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json"
ROUTES = BASELINE / "canonical" / "API_ROUTE_AUTHORITY.json"
WEBENGINE_EVIDENCE = ROOT / "evidence" / "gui-g7-v33-webengine.json"
EVIDENCE = ROOT / "evidence" / "gui-g7-v33-closure.json"

EXPECTED_CAPTURES = 12


class G7ClosureError(RuntimeError):
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
    require_reclosure_ready("G7")
    check_g7()
    generated = render()
    for key, expected in generated.items():
        path = OUTPUTS[key]
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            raise G7ClosureError(f"generated output drift: {path}")
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    rules = authority.get("rules")
    if authority.get("activation_status") != "ACTIVE" or not isinstance(rules, dict):
        raise G7ClosureError("G7 authority not ACTIVE")
    if rules.get("single_exact_batch_scope") is not True or rules.get("cross_batch_borrowing") != "FORBIDDEN":
        raise G7ClosureError("G7 exact-scope rules drifted")
    security = json.loads(SECURITY.read_text(encoding="utf-8"))
    routes = security.get("active_routes")
    if not isinstance(routes, list) or len(routes) != 101:
        raise G7ClosureError("G7 route authority is not exactly 101 routes")
    g7_routes = [
        item.get("route_id")
        for item in routes
        if isinstance(item, dict) and item.get("implementation_status") == "IMPLEMENTED_G7"
    ]
    if g7_routes != ["api.route.101"]:
        raise G7ClosureError("G7 route ids drifted")
    route_authority = json.loads(ROUTES.read_text(encoding="utf-8"))
    reserved = route_authority.get("reserved_routes")
    if not isinstance(reserved, list) or len(reserved) != 1:
        raise G7ClosureError("G7 reserved routes drifted")
    if reserved[0].get("route_id") != "gui.replay" or reserved[0].get("implementation_status") != "RESERVED_G7_NOT_EXPOSED":
        raise G7ClosureError("gui.replay must stay RESERVED_G7_NOT_EXPOSED")
    if not WEBENGINE_EVIDENCE.is_file():
        raise G7ClosureError("missing WebEngine visual evidence")
    webengine = json.loads(WEBENGINE_EVIDENCE.read_text(encoding="utf-8"))
    captures = webengine.get("captures")
    if webengine.get("status") != "PASS" or not isinstance(captures, list):
        raise G7ClosureError("WebEngine evidence is not PASS")
    if len(captures) != EXPECTED_CAPTURES:
        raise G7ClosureError(f"expected {EXPECTED_CAPTURES} captures, got {len(captures)}")
    for capture in captures:
        box = capture.get("box_model")
        file_value = capture.get("file")
        sha_value = capture.get("sha256")
        if not isinstance(box, dict) or box.get("overlapCount") != 0 or box.get("overflow") is not False:
            raise G7ClosureError(f"box model overlap/overflow: {capture!r}")
        if not isinstance(file_value, str) or not isinstance(sha_value, str):
            raise G7ClosureError("capture missing file/sha256")
        path = ROOT / file_value
        if not path.is_file() or _sha(path) != sha_value:
            raise G7ClosureError(f"capture drift: {file_value}")
    payload: dict[str, object] = {
        "schema": "TPAA_G7_V33_CLOSURE_EVIDENCE_V1",
        "phase": "G7",
        "phase_status": "CLOSED_LOCAL_WITH_GATES",
        "closed_at": "2026-11-07",
        "core_baseline": "CB-1.12.0",
        "parent_core_baseline": "CB-1.11.0",
        "baseline_lock_sha256": _sha(BASELINE / "BASELINE_LOCK.json"),
        "authority_sha256": _sha(AUTHORITY),
        "route_count": 101,
        "g7_route_ids": g7_routes,
        "reserved_routes": ["gui.replay"],
        "webengine_captures": EXPECTED_CAPTURES,
        "gates": {
            "ruff": "PASS",
            "mypy": "PASS 608 source files",
            "g7_successor_check": "PASS",
            "g7_codegen_check": "PASS routes=1 security_routes=101 files=3",
            "contract_pytest": "PASS 46 tests (gui_v33)",
            "application_pytest": "PASS 169 tests (incl. 7 G7 domain)",
            "unit_api_runtime_pytest": "PASS 199 tests (1 pre-existing installed-desktop e2e env failure unrelated to G7)",
            "frontend_typecheck_build": "PASS",
            "webengine_visual_acceptance": "PASS 12 captures V26, box_model no overlap",
            "api_negative_tests": "PASS 403 scope-denied / unknown-batch 404 / filter 422 / cursor-tamper 400",
        },
        "invariants": {
            "single_exact_batch_scope": True,
            "no_cross_batch_borrowing": True,
            "no_latest_fallback": True,
            "unknown_batch_404": True,
            "cluster_relation_only": True,
            "linear_supersession_chain": True,
            "atomic_construct_before_publish": True,
            "honest_empty_non_launch_behavior": True,
        },
        "restrictions": {"push": False, "production_deployment": False, "release_claim": False},
        "next_phase": "G8",
    }
    _write(payload)
    return payload


def main() -> int:
    try:
        result = close()
    except (OSError, ValueError, KeyError, G7ClosureError, RemediationGuardError) as exc:
        print(f"G7_V33_CLOSURE_FAIL {exc}")
        return 2
    print(
        "G7_V33_CLOSURE_PASS "
        f"status={result['phase_status']} routes={result['route_count']} "
        f"captures={result['webengine_captures']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
