#!/usr/bin/env python3
"""Build or verify the local G9 CB-1.14.0 Replay-context successor baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from tpaa_canonical.byte_stability import (
    GovernedTextRepresentation,
    canonicalize_governed_text_bytes,
    match_governed_text_bytes,
    normalize_governed_text_to_lf,
    write_utf8_lf,
)

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "baseline" / "CB-1.13.0"
PARENT_LOCK_SHA256 = "69ba7e442eafcaeb22072e42c4d078a6a5a1baa03393e478ac6f664a2e8e8b84"
TARGET = ROOT / "baseline" / "CB-1.14.0"
CORE = "CB-1.14.0"
DECISION_ID = "G9-V33-REPLAY-2026-11-07"
APPROVAL_ID = "G9-CB-1.14.0-LOCAL-IMPLEMENTATION-2026-11-07"


class G9SuccessorError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G9SuccessorError(f"expected JSON object: {path}")
    return value


def _clone(value: object) -> Any:
    return json.loads(json.dumps(value))


def _write(path: Path, value: Mapping[str, Any]) -> None:
    write_utf8_lf(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")

def _parent_artifact_entry(filename: str) -> dict[str, Any] | None:
    artifacts = _load(PARENT / "BASELINE_LOCK.json").get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("parent BASELINE_LOCK artifacts must be a list")
    for raw in artifacts:
        if not isinstance(raw, dict):
            raise ValueError("parent BASELINE_LOCK artifact entry must be an object")
        if raw.get("file") == filename:
            return cast(dict[str, Any], raw)
    return None


def _parent_representation(filename: str) -> GovernedTextRepresentation:
    entry = _parent_artifact_entry(filename)
    if entry is None:
        return "CRLF"
    expected_sha = entry.get("sha256")
    expected_bytes = entry.get("bytes")
    if not isinstance(expected_sha, str) or not isinstance(expected_bytes, int):
        raise ValueError(f"invalid parent lock entry for {filename}")
    _, matched = match_governed_text_bytes(
        (PARENT / "canonical" / filename).read_bytes(),
        expected_sha,
        expected_bytes,
    )
    return "CRLF" if matched == "CRLF" else "LF"


def _locked_bytes(path: Path) -> bytes:
    representation = _parent_representation(path.name)
    return canonicalize_governed_text_bytes(path.read_bytes(), representation)


def _locked_size(path: Path) -> int:
    return len(_locked_bytes(path))


def _sha256(path: Path) -> str:
    if path == PARENT / "BASELINE_LOCK.json":
        canonical, _ = match_governed_text_bytes(path.read_bytes(), PARENT_LOCK_SHA256)
        return hashlib.sha256(canonical).hexdigest()
    return hashlib.sha256(_locked_bytes(path)).hexdigest()

def _field(name: str, transport: str, *, source: str | None = None, required: bool = True) -> dict[str, Any]:
    return {"field": name, "source": source or f"g9.{name}", "required": required, "transport_type": transport}


# G9 activates the last reserved GUI route: exact WE replay context.  No reserved routes remain.
_ACTIVATED = (
    ("gui.replay", "GET", "/api/v1/gui/weapon-events/{weapon_event_id}/replay-context", "replay", "getGuiWeaponEventReplayContext", "ReplayContextDTO", "RAW_DATA_READ", "replay.read"),
)
_REMAINING_RESERVED: tuple[str, ...] = ()


def _dto() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "CROSS_LAYER_DTO_CONTRACTS.json"))
    value.update(core_baseline=CORE, authority_version="1.8.0", decision_id=DECISION_ID)
    contracts = value.get("contracts")
    if not isinstance(contracts, dict):
        raise G9SuccessorError("DTO contracts missing")
    replay = contracts.get("ReplayContextDTO")
    if not isinstance(replay, dict):
        raise G9SuccessorError("ReplayContextDTO missing")
    existing = {str(field.get("field")) for field in replay.get("fields", [])}
    for name, transport in (
        ("weapon_event_id", "uuid-string"),
        ("batch_id", "uuid-string"),
        ("perspective", "string"),
        ("t1_session_time_us", "string"),
        ("t2_session_time_us", "string?"),
        ("t3_session_time_us", "string?"),
        ("window_state", "string"),
        ("media_ranges", "object"),
    ):
        if name not in existing:
            replay.setdefault("fields", []).append(_field(name, transport))
    rules = value.setdefault("transport_rules", {})
    if not isinstance(rules, dict):
        raise G9SuccessorError("DTO rules invalid")
    rules["g9_replay"] = {
        "exact_we_scope": "REQUIRED",
        "latest_fallback": "FORBIDDEN",
        "unknown_we": "HTTP_404_UNDER_READY_BACKEND",
        "media_unavailable": "HONEST_EMPTY_RANGES",
        "drift": "EXPLICIT_STATE",
    }
    return cast(dict[str, Any], value)


def _routes() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "API_ROUTE_AUTHORITY.json"))
    value.update(authority_version="1.8.0", core_baseline=CORE, decision_id=DECISION_ID, approval_status="APPROVED_LOCAL")
    routes = value.get("routes")
    reserved = value.get("reserved_routes")
    if not isinstance(routes, list) or not isinstance(reserved, list):
        raise G9SuccessorError("route sections invalid")
    activated_ids = {row[0] for row in _ACTIVATED}
    remaining = []
    for item in reserved:
        if not isinstance(item, dict):
            continue
        if item.get("route_id") in activated_ids:
            continue
        if item.get("route_id") in _REMAINING_RESERVED:
            item["implementation_status"] = "RESERVED_G9_NOT_EXPOSED"
        remaining.append(item)
    value["reserved_routes"] = remaining
    for row in _ACTIVATED:
        logical, method, path, handler, operation, response, _permission, gui_permission = row
        routes.append(
            {
                "method": method,
                "path": path,
                "handler": handler,
                "operation_id": operation,
                "response_model": response,
                "module": "tpaa_api.gui_replay",
                "dto_authority": "CROSS_LAYER_DTO_CONTRACTS",
                "route_id": logical,
                "gui_permission_id": gui_permission,
                "implementation_status": "IMPLEMENTED_G9",
            }
        )
    return cast(dict[str, Any], value)


def _route_security() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json"))
    active = value.get("active_routes")
    if not isinstance(active, list) or len(active) != 102:
        raise G9SuccessorError("G8 security route count must be 102")
    for index, row in enumerate(_ACTIVATED, start=103):
        logical, method, path, handler, _operation, _response, permission, gui_permission = row
        active.append(
            {
                "route_id": f"api.route.{index:03d}",
                "method": method,
                "path": path,
                "module": "tpaa_api.gui_replay",
                "handler": handler,
                "authorization_mode": "BUSINESS_AND_GUI_PERMISSION",
                "permission_id": permission,
                "gui_permission_id": gui_permission,
                "audit_mode": "ALWAYS",
                "audit_event": f"{logical}.read",
                "implementation_status": "IMPLEMENTED_G9",
            }
        )
    value.update(
        authority_version="1.7.0",
        core_baseline=CORE,
        parent_core_baseline="CB-1.13.0",
        decision_id=DECISION_ID,
        approval_id=APPROVAL_ID,
        approval_status="APPROVED_LOCAL",
        activation_status="ACTIVE",
        release_claim=False,
    )
    value["mapping_basis"] = {
        "route_graph_source": "CB-1.13.0 plus one implemented G9 replay-context route",
        "route_count": 103,
        "stable_id_rule": "Preserve api.route.001-102; append G9 deterministically.",
    }
    return cast(dict[str, Any], value)


def _g9_authority() -> dict[str, Any]:
    return {
        "authority_id": "GUI_REPLAY_AUTHORITY",
        "authority_version": "1.0.0",
        "core_baseline": CORE,
        "parent_core_baseline": "CB-1.13.0",
        "decision_id": DECISION_ID,
        "approval_id": APPROVAL_ID,
        "activation_status": "ACTIVE",
        "rules": {
            "exact_we_scope": True,
            "latest_fallback": "FORBIDDEN",
            "unknown_we": "HTTP_404_UNDER_READY_BACKEND",
            "media_unavailable": "HONEST_EMPTY_RANGES",
            "drift": "EXPLICIT_STATE",
            "gui_business_recomputation": "FORBIDDEN",
            "browser_business_storage": "FORBIDDEN",
        },
        "single_owner_rules": {
            "replay_context_query": "tpaa_application.replay_context",
            "weapon_event_read_model": "tpaa_application.weapon_event",
            "event_window_resolver": "tpaa_application.event_window",
            "gui_business_recomputation": "FORBIDDEN",
            "browser_business_storage": "FORBIDDEN",
        },
        "database": {
            "schema": "1.10.0",
            "migration_required": False,
            "reason": "Replay context is an exact-WE read model over existing WE/Window facts; media ranges are honest-empty until the media pipeline is admitted.",
        },
        "release_claim": False,
    }


def _metadata(filename: str) -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / filename))
    value.update(
        core_baseline=CORE,
        parent_core_baseline="CB-1.13.0",
        decision_id=DECISION_ID,
        approval_id=APPROVAL_ID,
        approval_status="APPROVED_LOCAL",
        activation_status="ACTIVE",
        release_claim=False,
    )
    return cast(dict[str, Any], value)


def _schema_compatibility() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "SCHEMA_COMPATIBILITY_AUTHORITY.json"))
    value.update(
        authority_version="1.7.0",
        core_baseline=CORE,
        decision_id=DECISION_ID,
        approval_status="APPROVED",
        approval_date="2026-11-07",
        approval_basis="G9 local successor inherits unchanged CB-1.13.0 artifacts; no DB schema change.",
    )
    inherited: list[dict[str, str]] = []
    for path in sorted((PARENT / "canonical").glob("*.json"), key=lambda item: item.name):
        if path.name == "SCHEMA_COMPATIBILITY_AUTHORITY.json":
            continue
        payload = _load(path)
        declared = payload.get("core_baseline")
        if isinstance(declared, str) and declared != CORE:
            inherited.append(
                {
                    "file": path.name,
                    "declared_core_baseline": declared,
                    "compatible_core_baseline": CORE,
                    "approval_status": "APPROVED",
                }
            )
    value["core_inheritance"] = inherited
    entries = value.get("entries")
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict):
                entry["compatible_core_baseline"] = CORE
    return cast(dict[str, Any], value)


def build_successor(output: Path) -> None:
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(PARENT, output)
    canonical = output / "canonical"
    replacements = {
        "CROSS_LAYER_DTO_CONTRACTS.json": _dto(),
        "API_ROUTE_AUTHORITY.json": _routes(),
        "API_ROUTE_SECURITY_AUTHORITY.json": _route_security(),
        "GUI_PERMISSION_AUDIT_AUTHORITY.json": _metadata("GUI_PERMISSION_AUDIT_AUTHORITY.json"),
        "GUI_ROLE_VIEW_ACCESS_MATRIX.json": _metadata("GUI_ROLE_VIEW_ACCESS_MATRIX.json"),
        "GUI_VIEW_CONTRACT.json": _metadata("GUI_VIEW_CONTRACT.json"),
        "GUI_ASYNC_GATEWAY_AUTHORITY.json": _metadata("GUI_ASYNC_GATEWAY_AUTHORITY.json"),
        "GUI_BATCH_IMPORT_AUTHORITY.json": _metadata("GUI_BATCH_IMPORT_AUTHORITY.json"),
        "GUI_WEAPON_EVENT_AUTHORITY.json": _metadata("GUI_WEAPON_EVENT_AUTHORITY.json"),
        "GUI_HISTORICAL_OVERVIEW_AUTHORITY.json": _metadata("GUI_HISTORICAL_OVERVIEW_AUTHORITY.json"),
        "GUI_BATCH_EVENTS_AUTHORITY.json": _metadata("GUI_BATCH_EVENTS_AUTHORITY.json"),
        "GUI_CO_ATTACK_AUTHORITY.json": _metadata("GUI_CO_ATTACK_AUTHORITY.json"),
        "SCHEMA_COMPATIBILITY_AUTHORITY.json": _schema_compatibility(),
        "GUI_REPLAY_AUTHORITY.json": _g9_authority(),
        "G9_REPLAY_APPROVAL.json": {
            "schema": "TPAA_G9_REPLAY_APPROVAL_V1",
            "approval_id": APPROVAL_ID,
            "decision_id": DECISION_ID,
            "status": "APPROVED_LOCAL",
            "activation_status": "ACTIVE",
            "approved_core_baseline": CORE,
            "approved_at": "2026-11-07T00:00:00+08:00",
            "approver": "PROJECT_OWNER_G9_IMPLEMENTATION_DIRECTIVE",
            "restrictions": {"push": False, "production_deployment": False, "release_claim": False},
        },
    }
    for name, document in replacements.items():
        _write(canonical / name, document)
    artifacts = [
        {"file": path.name, "sha256": _sha256(path), "bytes": _locked_size(path)}
        for path in sorted(canonical.glob("*.json"), key=lambda item: item.name)
    ]
    _write(
        output / "BASELINE_LOCK.json",
        {
            "baseline": {
                "overall": "TPAA V8.0",
                "engineering": "ED-2.1",
                "core": CORE,
                "db_schema": "1.10.0",
                "product": "P1_METRIC_CATALOG-1.14.0",
                "date": "2026-11-07",
                "rebaseline": "R3.9_G9_REPLAY",
                "decision_id": DECISION_ID,
                "approval_id": APPROVAL_ID,
                "approval_status": "APPROVED_LOCAL",
                "activation_status": "ACTIVE",
                "lock_lineage_sha256": [_sha256(PARENT / "BASELINE_LOCK.json")],
                "release_claim": False,
            },
            "artifacts": artifacts,
        },
    )
    _write(
        output / "IMPORT_PROVENANCE.json",
        {
            "record_type": "G9_SUCCESSOR_IMPORT_PROVENANCE",
            "authority": False,
            "decision_id": DECISION_ID,
            "source_baseline": "CB-1.13.0",
            "source_baseline_lock_sha256": _sha256(PARENT / "BASELINE_LOCK.json"),
            "core_baseline": CORE,
            "db_schema_target": "1.10.0",
            "controlled_artifact_count": len(artifacts),
            "release_claim": False,
        },
    )
    (output / "README.md").write_text(
        "# CB-1.14.0 G9 Replay-context successor baseline\n\n"
        f"Decision: `{DECISION_ID}`. CB-1.13.0 remains the immutable parent. "
        "This local successor activates the exact-WE replay-context read route and does not authorize push or deployment.\n",
        encoding="utf-8",
    )


def _digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(normalize_governed_text_to_lf(path.read_bytes()))
            digest.update(b"\0")
    return digest.hexdigest()


def check_successor() -> None:
    if not TARGET.is_dir():
        raise G9SuccessorError(f"successor missing: {TARGET}")
    with tempfile.TemporaryDirectory(prefix="tpaa-g9-successor-") as temporary:
        expected = Path(temporary) / CORE
        build_successor(expected)
        expected_digest = _digest(expected)
    actual = _digest(TARGET)
    if actual != expected_digest:
        raise G9SuccessorError(f"successor drift: {actual} != {expected_digest}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        check_successor() if args.check else build_successor(TARGET)
        print(f"G9_SUCCESSOR_PASS core={CORE} digest={_digest(TARGET)}")
    except (OSError, ValueError, KeyError, G9SuccessorError) as exc:
        print(f"G9_SUCCESSOR_FAIL {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
