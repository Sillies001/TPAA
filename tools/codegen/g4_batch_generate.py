#!/usr/bin/env python3
"""Generate CB-1.9.0 G4 security, gateway and TypeScript Batch authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.9.0"
CANONICAL = BASELINE / "canonical"
OUTPUTS = {
    "security": ROOT / "src" / "tpaa_security" / "generated_g4_authority.py",
    "application": ROOT / "src" / "tpaa_application" / "generated_g4_gateway.py",
    "typescript": ROOT / "frontend" / "gui-v33" / "src" / "generated" / "g4-batch.ts",
}
MANIFEST = ROOT / "generated" / "g4-cb-1.9.0" / "manifest.json"


class G4CodegenError(RuntimeError):
    pass


def _load(name: str) -> dict[str, Any]:
    value = json.loads((CANONICAL / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G4CodegenError(f"expected object: {name}")
    return value


def _objects(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise G4CodegenError(f"expected object array: {label}")
    return list(value)


def _strings(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise G4CodegenError(f"expected strings: {label}")
    return tuple(value)


def _security() -> str:
    gui = _load("GUI_PERMISSION_AUDIT_AUTHORITY.json")
    route_authority = _load("API_ROUTE_SECURITY_AUTHORITY.json")
    role_authority = gui.get("role_authority")
    if not isinstance(role_authority, dict):
        raise G4CodegenError("role authority invalid")
    bindings = _objects(gui.get("business_permission_bindings"), "GUI bindings")
    routes = _objects(route_authority.get("active_routes"), "active routes")
    if len(routes) != 96:
        raise G4CodegenError("G4 route authority must contain 96 routes")
    gui_rows = []
    for item in bindings:
        gui_rows.append(
            (
                str(item["permission_id"]),
                str(item["binding_type"]),
                _strings(item.get("business_permissions"), "business permissions"),
            )
        )
    route_rows = []
    for item in routes:
        permission = item.get("permission_id")
        gui_permission = item.get("gui_permission_id")
        if permission is not None and not isinstance(permission, str):
            raise G4CodegenError("route permission invalid")
        if gui_permission is not None and not isinstance(gui_permission, str):
            raise G4CodegenError("GUI route permission invalid")
        route_rows.append(
            (
                str(item["route_id"]),
                str(item["method"]),
                str(item["path"]),
                permission,
                str(item["audit_mode"]),
                gui_permission,
            )
        )
    lines = [
        '\"\"\"Generated from approved CB-1.9.0 authorities; do not edit manually.\"\"\"',
        "",
        "from typing import Final",
        "",
        "CORE_BASELINE: Final = 'CB-1.9.0'",
        f"GUI_AUTHORITY_ID: Final = {gui['authority_id']!r}",
        f"GUI_AUTHORITY_VERSION: Final = {gui['authority_version']!r}",
        "GUI_ACTIVATION_STATUS: Final = 'ACTIVE'",
        f"KNOWN_GUI_ROLES: Final[tuple[str, ...]] = {_strings(role_authority.get('role_ids'), 'roles')!r}",
        "GUI_PERMISSION_BINDINGS: Final[tuple[tuple[str, str, tuple[str, ...]], ...]] = (",
    ]
    lines.extend(f"    {row!r}," for row in gui_rows)
    lines.extend(
        [
            ")",
            "ROUTE_SECURITY_BINDINGS: Final[tuple[tuple[str, str, str, str | None, str, str | None], ...]] = (",
        ]
    )
    lines.extend(f"    {row!r}," for row in route_rows)
    lines.extend([")", ""])
    return "\n".join(lines)


def _application() -> str:
    parent = (ROOT / "src" / "tpaa_application" / "generated_g3_gateway.py").read_text(
        encoding="utf-8"
    )
    return parent.replace("Generated G3", "Generated G4").replace("CB-1.8.0", "CB-1.9.0")


def _typescript() -> str:
    authority = _load("GUI_BATCH_IMPORT_AUTHORITY.json")
    routes = _objects(_load("API_ROUTE_AUTHORITY.json").get("routes"), "routes")
    g4_routes = {
        str(item["route_id"]): {
            "method": item["method"],
            "path": item["path"],
            "responseDto": item["response_model"],
        }
        for item in routes
        if item.get("implementation_status") == "IMPLEMENTED_G4"
    }
    return f"""// @generated from CB-1.9.0 GUI_BATCH_IMPORT_AUTHORITY; DO NOT EDIT.

export type BatchTrainingType =
  | "SIMPLE_OPPOSITION"
  | "MIXED_OPPOSITION"
  | "COMPREHENSIVE_OPPOSITION"
  | "UNCLASSIFIED";
export type BatchQualificationStatus =
  | "PENDING_CONFIRMATION"
  | "PARSING"
  | "QUALIFIED"
  | "FAILED";

export interface ImportTicketDTO {{
  readonly schema: "TPAA_G4_IMPORT_TICKET_V1";
  readonly ticket_id: string;
  readonly kind: "FILE" | "DIRECTORY";
  readonly entry_count: number;
  readonly size_bytes: number;
  readonly manifest_sha256: string;
  readonly expires_at: string;
  readonly local_path: null;
}}

export interface BatchRegistrationDTO {{
  readonly schema: "TPAA_G4_BATCH_REGISTRATION_V1";
  readonly batch_id: string;
  readonly session_id: string;
  readonly batch_date: string;
  readonly batch_training_type: BatchTrainingType;
  readonly training_type_confirmed: boolean;
  readonly context_id: string | null;
  readonly release_id: string | null;
  readonly qualification_status: BatchQualificationStatus;
  readonly source_manifest_sha256: string;
  readonly revision_no: number;
  readonly created_by: string;
  readonly created_at: string;
  readonly reason_code: string | null;
  readonly v01_eligible: boolean;
}}

export interface BatchListDTO {{
  readonly schema: "TPAA_G4_BATCH_LIST_V1";
  readonly items: readonly BatchRegistrationDTO[];
  readonly total_count: number;
}}

export interface ForceFormationMemberDTO {{
  readonly aircraft_id: string;
  readonly formation_id: string | null;
  readonly side: "RED" | "BLUE" | "NEUTRAL" | "UNASSIGNED" | "CONFLICT";
  readonly member_role: string;
  readonly independent_target: boolean;
}}

export interface ForceFormationContextDTO {{
  readonly schema: "TPAA_G4_FORCE_FORMATION_CONTEXT_V1";
  readonly context_revision_id: string;
  readonly context_id: string;
  readonly revision_no: number;
  readonly valid_from_session_time_us: number;
  readonly valid_to_session_time_us: number | null;
  readonly source: string;
  readonly reason: string;
  readonly changed_by: string;
  readonly members: readonly ForceFormationMemberDTO[];
}}

export const G4_BATCH_ROUTES = {json.dumps(g4_routes, ensure_ascii=False, indent=2, sort_keys=True)} as const;
export const G4_BATCH_AUTHORITY = {json.dumps(authority, ensure_ascii=False, indent=2, sort_keys=True)} as const;
"""


def render() -> dict[str, str]:
    approval = _load("G4_BATCH_IMPORT_APPROVAL.json")
    if approval.get("status") != "APPROVED_LOCAL" or approval.get("activation_status") != "ACTIVE":
        raise G4CodegenError("G4 authority is not active")
    return {"security": _security(), "application": _application(), "typescript": _typescript()}


def _manifest(rendered: Mapping[str, str]) -> dict[str, Any]:
    files = []
    for key, content in rendered.items():
        raw = content.encode("utf-8")
        files.append(
            {
                "key": key,
                "path": OUTPUTS[key].relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
        )
    return {
        "schema": "TPAA_G4_BATCH_GENERATION_MANIFEST_V1",
        "core_baseline": "CB-1.9.0",
        "baseline_lock_sha256": hashlib.sha256((BASELINE / "BASELINE_LOCK.json").read_bytes()).hexdigest(),
        "files": sorted(files, key=lambda item: item["path"]),
        "release_claim": False,
    }


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", delete=False, dir=path.parent) as temporary:
        temporary.write(content)
        candidate = Path(temporary.name)
    candidate.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        rendered = render()
        manifest = json.dumps(_manifest(rendered), ensure_ascii=False, indent=2) + "\n"
        if args.check:
            for key, content in rendered.items():
                if not OUTPUTS[key].is_file() or OUTPUTS[key].read_text(encoding="utf-8") != content:
                    raise G4CodegenError(f"generated output drift: {OUTPUTS[key]}")
            if not MANIFEST.is_file() or MANIFEST.read_text(encoding="utf-8") != manifest:
                raise G4CodegenError("manifest drift")
        else:
            for key, content in rendered.items():
                _write(OUTPUTS[key], content)
            _write(MANIFEST, manifest)
        print("G4_BATCH_CODEGEN_PASS routes=7 security_routes=96")
    except (OSError, ValueError, KeyError, G4CodegenError) as exc:
        print(f"G4_BATCH_CODEGEN_FAIL {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
