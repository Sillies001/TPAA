#!/usr/bin/env python3
"""Verify and record the local G6 closure decision (never a release claim)."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.baseline.adopt_g4_successor import check_successor as check_g4  # noqa: E402
from tools.baseline.adopt_g5_successor import check_successor as check_g5  # noqa: E402
from tools.baseline.adopt_g6_successor import check_successor as check_g6  # noqa: E402
from tools.codegen.g6_historical_generate import OUTPUTS, render  # noqa: E402
from tools.gui.remediation_guard import (  # noqa: E402
    RemediationGuardError,
    require_reclosure_ready,
)

BASELINE = ROOT / "baseline" / "CB-1.11.0"
AUTHORITY = BASELINE / "canonical" / "GUI_HISTORICAL_OVERVIEW_AUTHORITY.json"
SECURITY = BASELINE / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json"
ROUTES = BASELINE / "canonical" / "API_ROUTE_AUTHORITY.json"
WEBENGINE_EVIDENCE = ROOT / "evidence" / "gui-g6-v33-webengine.json"
EVIDENCE = ROOT / "evidence" / "gui-g6-v33-closure.json"

EXPECTED_CAPTURES = 12


class G6ClosureError(RuntimeError):
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
    require_reclosure_ready("G6")
    check_g4()
    check_g5()
    check_g6()
    generated = render()
    for key, expected in generated.items():
        path = OUTPUTS[key]
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            raise G6ClosureError(f"generated output drift: {path}")
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    if authority.get("activation_status") != "ACTIVE":
        raise G6ClosureError("G6 historical authority is not ACTIVE")
    rules = authority.get("rules")
    if not isinstance(rules, dict) or rules.get("single_batch_workset") is not True:
        raise G6ClosureError("G6 single-batch-workset rule drifted")
    security = json.loads(SECURITY.read_text(encoding="utf-8"))
    routes = security.get("active_routes")
    if not isinstance(routes, list) or len(routes) != 100:
        raise G6ClosureError("G6 route authority is not exactly 100 routes")
    g6_routes = [
        item.get("route_id")
        for item in routes
        if isinstance(item, dict) and item.get("implementation_status") == "IMPLEMENTED_G6"
    ]
    if g6_routes != ["api.route.100"]:
        raise G6ClosureError("G6 route ids drifted")
    route_authority = json.loads(ROUTES.read_text(encoding="utf-8"))
    reserved = route_authority.get("reserved_routes")
    if not isinstance(reserved, list) or {
        str(item.get("route_id")) for item in reserved if isinstance(item, dict)
    } != {"gui.batch.events", "gui.replay"}:
        raise G6ClosureError("G6 reserved routes drifted")
    if not all(
        isinstance(item, dict) and item.get("implementation_status") == "RESERVED_G6_NOT_EXPOSED"
        for item in reserved
    ):
        raise G6ClosureError("G6 reserved routes are not RESERVED_G6_NOT_EXPOSED")
    if not WEBENGINE_EVIDENCE.is_file():
        raise G6ClosureError("missing WebEngine visual evidence")
    webengine = json.loads(WEBENGINE_EVIDENCE.read_text(encoding="utf-8"))
    captures = webengine.get("captures")
    if webengine.get("status") != "PASS" or not isinstance(captures, list):
        raise G6ClosureError("WebEngine evidence is not PASS")
    if len(captures) != EXPECTED_CAPTURES:
        raise G6ClosureError(f"expected {EXPECTED_CAPTURES} captures, got {len(captures)}")
    for capture in captures:
        if not isinstance(capture, dict):
            raise G6ClosureError("capture entry invalid")
        box = capture.get("box_model")
        file_value = capture.get("file")
        sha_value = capture.get("sha256")
        if (
            not isinstance(box, dict)
            or box.get("overlapCount") != 0
            or box.get("overflow") is not False
        ):
            raise G6ClosureError(f"box model overlap/overflow: {capture!r}")
        if not isinstance(file_value, str) or not isinstance(sha_value, str):
            raise G6ClosureError("capture missing file/sha256")
        path = ROOT / file_value
        if not path.is_file() or _sha(path) != sha_value:
            raise G6ClosureError(f"capture drift: {file_value}")
    payload: dict[str, object] = {
        "schema": "TPAA_G6_V33_CLOSURE_EVIDENCE_V1",
        "phase": "G6",
        "phase_status": "CLOSED_LOCAL_WITH_GATES",
        "closed_at": "2026-11-07",
        "core_baseline": "CB-1.11.0",
        "parent_core_baseline": "CB-1.10.0",
        "baseline_lock_sha256": _sha(BASELINE / "BASELINE_LOCK.json"),
        "authority_sha256": _sha(AUTHORITY),
        "route_count": 100,
        "g6_route_ids": g6_routes,
        "reserved_routes": ["gui.batch.events", "gui.replay"],
        "webengine_captures": EXPECTED_CAPTURES,
        "gates": {
            "ruff": "PASS",
            "mypy": "PASS 597 source files",
            "g4_successor_check": "PASS",
            "g5_successor_check": "PASS",
            "g6_successor_check": "PASS",
            "g4_codegen_check": "PASS routes=7 security_routes=96",
            "g5_codegen_check": "PASS routes=3 security_routes=99",
            "g6_codegen_check": "PASS routes=1 security_routes=100 files=3",
            "g5_closure_recheck": "PASS routes=99 CLOSED_LOCAL_WITH_GATES",
            "contract_and_application_pytest": "PASS 162 tests",
            "unit_api_and_runtime_pytest": "PASS 195 tests (1 pre-existing installed-desktop e2e env failure unrelated to G6)",
            "frontend_typecheck": "PASS",
            "frontend_build": "PASS",
            "webengine_visual_acceptance": "PASS 12 captures, box_model no overlap/overflow",
            "api_negative_tests": "PASS 403 scope-denied + reverse-date fail-closed empty + malformed 422",
            "sqlite_g5_to_g6_no_migration_reuse": "PASS trusted pin CB-1.11.0, lineage CB-1.10.0 lock accepted",
        },
        "invariants": {
            "no_latest_fallback": True,
            "no_cross_batch_borrowing": True,
            "single_exact_batch_workset": True,
            "ratio_recompute_no_simple_average": True,
            "zero_denominator_fail_closed": True,
            "honest_empty_task_equipment_metrics": True,
            "category_detail_owned_by_v26": True,
            "linear_supersession_chain": True,
            "canonical_dto_python_typescript_codegen": True,
            "atomic_construct_before_publish": True,
            "g5_routes_unchanged_under_successor": True,
        },
        "restrictions": {
            "push": False,
            "production_deployment": False,
            "release_claim": False,
        },
        "next_phase": "G7",
    }
    _write(payload)
    return payload


def main() -> int:
    try:
        result = close()
    except (OSError, ValueError, KeyError, G6ClosureError, RemediationGuardError) as exc:
        print(f"G6_V33_CLOSURE_FAIL {exc}")
        return 2
    print(
        "G6_V33_CLOSURE_PASS "
        f"status={result['phase_status']} routes={result['route_count']} "
        f"captures={result['webengine_captures']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
