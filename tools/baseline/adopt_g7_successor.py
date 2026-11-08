#!/usr/bin/env python3
"""Build or verify the local G7 CB-1.12.0 Batch-events successor baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "baseline" / "CB-1.11.0"
TARGET = ROOT / "baseline" / "CB-1.12.0"
CORE = "CB-1.12.0"
DECISION_ID = "G7-V33-BATCH-EVENTS-2026-11-07"
APPROVAL_ID = "G7-CB-1.12.0-LOCAL-IMPLEMENTATION-2026-11-07"


class G7SuccessorError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G7SuccessorError(f"expected JSON object: {path}")
    return value


def _clone(value: object) -> Any:
    return json.loads(json.dumps(value))


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _field(name: str, transport: str, *, source: str | None = None) -> dict[str, Any]:
    return {
        "field": name,
        "source": source or f"g7.{name}",
        "required": True,
        "transport_type": transport,
    }


# G7 activates exactly the V26 batch-events workbench read route.  gui.replay (G9)
# stays reserved.  All KPIs/lists share one exact Batch scope; no cross-batch borrowing.
_ACTIVATED = (
    ("gui.batch.events", "GET", "/api/v1/gui/batches/{batch_id}/weapon-events", "batch_events", "getGuiBatchWeaponEvents", "BatchEventWorkbenchDTO", "DERIVED_DATA_READ", "weapon_event.read"),
)
_REMAINING_RESERVED = ("gui.replay",)

_LIST_ITEM_ADDITIONS = (
    ("batch_id", "uuid-string"),
    ("t1_session_time_us", "string"),
    ("shooter_entity_id", "uuid-string"),
    ("target_entity_id", "uuid-string?"),
    ("episode_id", "uuid-string?"),
    ("weapon_terminal_state", "string"),
    ("adjudication_state", "string"),
    ("observation_window_state", "string"),
    ("classification_exception", "boolean"),
)


def _dto() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "CROSS_LAYER_DTO_CONTRACTS.json"))
    value.update(core_baseline=CORE, authority_version="1.6.0", decision_id=DECISION_ID)
    contracts = value.get("contracts")
    if not isinstance(contracts, dict):
        raise G7SuccessorError("DTO contracts missing")
    list_item = contracts.get("WeaponEventListItemDTO")
    if not isinstance(list_item, dict):
        raise G7SuccessorError("WeaponEventListItemDTO missing")
    existing = {str(field.get("field")) for field in list_item.get("fields", [])}
    for name, transport in _LIST_ITEM_ADDITIONS:
        if name not in existing:
            list_item.setdefault("fields", []).append(_field(name, transport))
    common = [_field("schema", "string"), _field("provenance", "object")]
    contracts["BatchEventWorkbenchDTO"] = {"fields": common + [
        _field("request_id", "string"),
        _field("query_context_id", "string"),
        _field("batch_id", "uuid-string"),
        _field("filter", "object"),
        _field("summary", "object"),
        _field("items", "object"),
        _field("next_cursor", "string?", source="g7.next_cursor"),
        _field("total_count", "integer"),
    ]}
    rules = value.setdefault("transport_rules", {})
    if not isinstance(rules, dict):
        raise G7SuccessorError("DTO rules invalid")
    rules["g7_batch_events"] = {
        "single_exact_batch_scope": "REQUIRED",
        "cross_batch_borrowing": "FORBIDDEN",
        "cursor": "OPAQUE_VERSIONED_CHECKSUMMED",
        "unknown_batch": "HTTP_404_UNDER_READY_BACKEND",
        "gui_business_recomputation": "FORBIDDEN",
    }
    return cast(dict[str, Any], value)


def _routes() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "API_ROUTE_AUTHORITY.json"))
    value.update(authority_version="1.6.0", core_baseline=CORE, decision_id=DECISION_ID, approval_status="APPROVED_LOCAL")
    routes = value.get("routes")
    reserved = value.get("reserved_routes")
    if not isinstance(routes, list) or not isinstance(reserved, list):
        raise G7SuccessorError("route sections invalid")
    activated_ids = {row[0] for row in _ACTIVATED}
    remaining = []
    for item in reserved:
        if not isinstance(item, dict):
            continue
        if item.get("route_id") in activated_ids:
            continue
        if item.get("route_id") in _REMAINING_RESERVED:
            item["implementation_status"] = "RESERVED_G7_NOT_EXPOSED"
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
                "module": "tpaa_api.gui_batch_events",
                "dto_authority": "CROSS_LAYER_DTO_CONTRACTS",
                "route_id": logical,
                "gui_permission_id": gui_permission,
                "implementation_status": "IMPLEMENTED_G7",
            }
        )
    return cast(dict[str, Any], value)


def _route_security() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json"))
    active = value.get("active_routes")
    if not isinstance(active, list) or len(active) != 100:
        raise G7SuccessorError("G6 security route count must be 100")
    for index, row in enumerate(_ACTIVATED, start=101):
        logical, method, path, handler, _operation, _response, permission, gui_permission = row
        active.append(
            {
                "route_id": f"api.route.{index:03d}",
                "method": method,
                "path": path,
                "module": "tpaa_api.gui_batch_events",
                "handler": handler,
                "authorization_mode": "BUSINESS_AND_GUI_PERMISSION",
                "permission_id": permission,
                "gui_permission_id": gui_permission,
                "audit_mode": "ALWAYS",
                "audit_event": f"{logical}.read",
                "implementation_status": "IMPLEMENTED_G7",
            }
        )
    value.update(
        authority_version="1.5.0",
        core_baseline=CORE,
        parent_core_baseline="CB-1.11.0",
        decision_id=DECISION_ID,
        approval_id=APPROVAL_ID,
        approval_status="APPROVED_LOCAL",
        activation_status="ACTIVE",
        release_claim=False,
    )
    value["mapping_basis"] = {
        "route_graph_source": "CB-1.11.0 plus one implemented G7 batch-events route",
        "route_count": 101,
        "stable_id_rule": "Preserve api.route.001-100; append G7 deterministically.",
    }
    return cast(dict[str, Any], value)


def _g7_authority() -> dict[str, Any]:
    return {
        "authority_id": "GUI_BATCH_EVENTS_AUTHORITY",
        "authority_version": "1.0.0",
        "core_baseline": CORE,
        "parent_core_baseline": "CB-1.11.0",
        "decision_id": DECISION_ID,
        "approval_id": APPROVAL_ID,
        "activation_status": "ACTIVE",
        "rules": {
            "single_exact_batch_scope": True,
            "cross_batch_borrowing": "FORBIDDEN",
            "unknown_batch": "HTTP_404_UNDER_READY_BACKEND",
            "cursor": "OPAQUE_VERSIONED_CHECKSUMMED",
            "latest_fallback": "FORBIDDEN",
            "cluster_relation_only": True,
            "non_launch_behavior_source": "NOT_ADMITTED_G10_SOURCE_MATRIX",
            "gui_business_recomputation": "FORBIDDEN",
            "browser_business_storage": "FORBIDDEN",
        },
        "single_owner_rules": {
            "batch_events_query": "tpaa_application.batch_events",
            "weapon_event_detector": "tpaa_application.weapon_event",
            "weapon_event_identity": "tpaa_application.weapon_event",
            "attack_cluster_resolver": "tpaa_application.weapon_event",
            "gui_business_recomputation": "FORBIDDEN",
            "browser_business_storage": "FORBIDDEN",
        },
        "database": {
            "schema": "1.10.0",
            "migration_required": False,
            "reason": "Batch events is an exact-batch read model over existing Batch/WE/Cluster relations; no new physical tables.",
        },
        "release_claim": False,
    }


def _metadata(filename: str) -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / filename))
    value.update(
        core_baseline=CORE,
        parent_core_baseline="CB-1.11.0",
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
        authority_version="1.5.0",
        core_baseline=CORE,
        decision_id=DECISION_ID,
        approval_status="APPROVED",
        approval_date="2026-11-07",
        approval_basis="G7 local successor inherits unchanged CB-1.11.0 artifacts; no DB schema change.",
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
        "SCHEMA_COMPATIBILITY_AUTHORITY.json": _schema_compatibility(),
        "GUI_BATCH_EVENTS_AUTHORITY.json": _g7_authority(),
        "G7_BATCH_EVENTS_APPROVAL.json": {
            "schema": "TPAA_G7_BATCH_EVENTS_APPROVAL_V1",
            "approval_id": APPROVAL_ID,
            "decision_id": DECISION_ID,
            "status": "APPROVED_LOCAL",
            "activation_status": "ACTIVE",
            "approved_core_baseline": CORE,
            "approved_at": "2026-11-07T00:00:00+08:00",
            "approver": "PROJECT_OWNER_G7_IMPLEMENTATION_DIRECTIVE",
            "restrictions": {"push": False, "production_deployment": False, "release_claim": False},
        },
    }
    for name, document in replacements.items():
        _write(canonical / name, document)
    artifacts = [
        {"file": path.name, "sha256": _sha256(path), "bytes": path.stat().st_size}
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
                "rebaseline": "R3.7_G7_BATCH_EVENTS",
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
            "record_type": "G7_SUCCESSOR_IMPORT_PROVENANCE",
            "authority": False,
            "decision_id": DECISION_ID,
            "source_baseline": "CB-1.11.0",
            "source_baseline_lock_sha256": _sha256(PARENT / "BASELINE_LOCK.json"),
            "core_baseline": CORE,
            "db_schema_target": "1.10.0",
            "controlled_artifact_count": len(artifacts),
            "release_claim": False,
        },
    )
    (output / "README.md").write_text(
        "# CB-1.12.0 G7 Batch-events successor baseline\n\n"
        f"Decision: `{DECISION_ID}`. CB-1.11.0 remains the immutable parent. "
        "This local successor activates only the V26 batch-events workbench read route and does not authorize push or deployment.\n",
        encoding="utf-8",
    )


def _digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def check_successor() -> None:
    if not TARGET.is_dir():
        raise G7SuccessorError(f"successor missing: {TARGET}")
    with tempfile.TemporaryDirectory(prefix="tpaa-g7-successor-") as temporary:
        expected = Path(temporary) / CORE
        build_successor(expected)
        expected_digest = _digest(expected)
    actual = _digest(TARGET)
    if actual != expected_digest:
        raise G7SuccessorError(f"successor drift: {actual} != {expected_digest}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        check_successor() if args.check else build_successor(TARGET)
        print(f"G7_SUCCESSOR_PASS core={CORE} digest={_digest(TARGET)}")
    except (OSError, ValueError, KeyError, G7SuccessorError) as exc:
        print(f"G7_SUCCESSOR_FAIL {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
