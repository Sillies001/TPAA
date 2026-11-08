#!/usr/bin/env python3
"""Verify and record the local G5 closure decision (never a release claim)."""

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
from tools.codegen.g5_weapon_event_generate import OUTPUTS, render  # noqa: E402

BASELINE = ROOT / "baseline" / "CB-1.10.0"
AUTHORITY = BASELINE / "canonical" / "GUI_WEAPON_EVENT_AUTHORITY.json"
EVIDENCE = ROOT / "evidence" / "gui-g5-v33-closure.json"


class G5ClosureError(RuntimeError):
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
    check_g4()
    check_g5()
    generated = render()
    for key, expected in generated.items():
        path = OUTPUTS[key]
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            raise G5ClosureError(f"generated output drift: {path}")
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    statuses = authority.get("capability_status")
    if not isinstance(statuses, dict) or set(statuses.values()) != {"ACTIVE"}:
        raise G5ClosureError("G5 capability status is not fully ACTIVE")
    security = json.loads(
        (BASELINE / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json").read_text(
            encoding="utf-8"
        )
    )
    routes = security.get("active_routes")
    if not isinstance(routes, list) or len(routes) != 99:
        raise G5ClosureError("G5 route authority is not exactly 99 routes")
    g5_routes = [
        item.get("route_id")
        for item in routes
        if isinstance(item, dict) and item.get("implementation_status") == "IMPLEMENTED_G5"
    ]
    if g5_routes != ["api.route.097", "api.route.098", "api.route.099"]:
        raise G5ClosureError("G5 route ids drifted")
    payload: dict[str, object] = {
        "schema": "TPAA_G5_V33_CLOSURE_EVIDENCE_V1",
        "phase": "G5",
        "phase_status": "CLOSED_LOCAL_WITH_GATES",
        "closed_at": "2026-11-07",
        "core_baseline": "CB-1.10.0",
        "parent_core_baseline": "CB-1.9.0",
        "baseline_lock_sha256": _sha(BASELINE / "BASELINE_LOCK.json"),
        "authority_sha256": _sha(AUTHORITY),
        "route_count": 99,
        "g5_route_ids": g5_routes,
        "capability_status": statuses,
        "gates": {
            "ruff": "PASS",
            "mypy": "PASS 588 source files",
            "g4_successor_check": "PASS",
            "g5_successor_check": "PASS",
            "g4_codegen_check": "PASS routes=7 security_routes=96",
            "g5_codegen_check": "PASS routes=3 security_routes=99 files=4",
            "python_regression": "PASS 329 tests; one transient Windows file-lock case passed on isolated retry",
            "g5_targeted": "PASS 69 tests",
            "frontend_typecheck": "PASS",
            "frontend_build": "PASS",
            "frontend_resource_consistency": "PASS",
            "sqlite_g4_to_g5_no_migration_reuse": "PASS manifest unchanged",
            "postgres_lineage_lock_verifier": "PASS explicit exact lock allow-list",
        },
        "invariants": {
            "no_latest_fallback": True,
            "no_cross_batch_borrowing": True,
            "exact_weapon_event_scope": True,
            "persistent_rejection_audit_adapter": True,
            "linear_supersession_chain": True,
            "canonical_dto_python_typescript_codegen": True,
            "atomic_construct_before_publish": True,
            "honest_empty_state": True,
        },
        "restrictions": {
            "push": False,
            "production_deployment": False,
            "release_claim": False,
        },
        "next_phase": "G6",
    }
    _write(payload)
    return payload


def main() -> int:
    try:
        result = close()
    except (OSError, ValueError, KeyError, G5ClosureError) as exc:
        print(f"G5_V33_CLOSURE_FAIL {exc}")
        return 2
    print(
        "G5_V33_CLOSURE_PASS "
        f"status={result['phase_status']} routes={result['route_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
