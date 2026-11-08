#!/usr/bin/env python3
"""Build or verify the local G8 CB-1.13.0 Co-attack-analysis successor baseline."""

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
PARENT = ROOT / "baseline" / "CB-1.12.0"
TARGET = ROOT / "baseline" / "CB-1.13.0"
CORE = "CB-1.13.0"
DECISION_ID = "G8-V33-CO-ATTACK-2026-11-07"
APPROVAL_ID = "G8-CB-1.13.0-LOCAL-IMPLEMENTATION-2026-11-07"


class G8SuccessorError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G8SuccessorError(f"expected JSON object: {path}")
    return value


def _clone(value: object) -> Any:
    return json.loads(json.dumps(value))


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _field(name: str, transport: str, *, source: str | None = None) -> dict[str, Any]:
    return {"field": name, "source": source or f"g8.{name}", "required": True, "transport_type": transport}


# G8 activates exactly the V24 co-attack analysis read route (BVR formation clusters only).
# gui.replay (G9) stays reserved.  Strike clusters are rejected fail-closed by authority.
_ACTIVATED = (
    ("gui.coattack", "GET", "/api/v1/gui/attack-clusters/{cluster_id}/co-attack-analysis", "co_attack", "getGuiCoAttackAnalysis", "CoAttackAnalysisDTO", "DERIVED_DATA_READ", "weapon_event.read"),
)
_REMAINING_RESERVED = ("gui.replay",)


def _dto() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "CROSS_LAYER_DTO_CONTRACTS.json"))
    value.update(core_baseline=CORE, authority_version="1.7.0", decision_id=DECISION_ID)
    contracts = value.get("contracts")
    if not isinstance(contracts, dict):
        raise G8SuccessorError("DTO contracts missing")
    workbench = contracts.get("BatchEventWorkbenchDTO")
    if isinstance(workbench, dict):
        existing = {str(field.get("field")) for field in workbench.get("fields", [])}
        if "batch_context_id" not in existing:
            workbench.setdefault("fields", []).append(
                {"field": "batch_context_id", "source": "g8.batch_context_id", "required": False, "transport_type": "uuid-string?"}
            )
    common = [_field("schema", "string"), _field("provenance", "object")]
    contracts["CoAttackAnalysisDTO"] = {"fields": common + [
        _field("request_id", "string"),
        _field("query_context_id", "string"),
        _field("cluster_id", "uuid-string"),
        _field("batch_id", "uuid-string"),
        _field("context_id", "uuid-string?"),
        _field("batch_context_id", "uuid-string?"),
        _field("filter", "object"),
        _field("weapon_events", "object"),
        _field("formation", "object"),
        _field("dimensions", "object"),
    ]}
    rules = value.setdefault("transport_rules", {})
    if not isinstance(rules, dict):
        raise G8SuccessorError("DTO rules invalid")
    rules["g8_co_attack"] = {
        "cluster_scope": "EXACT_CLUSTER_RELATION_ONLY",
        "cross_batch_cluster": "FORBIDDEN",
        "bvr_only": True,
        "strike_cluster_rejected": "FAIL_CLOSED",
        "missing_context": "HONEST_EMPTY_FORMATION",
        "no_total_score": True,
        "gui_business_recomputation": "FORBIDDEN",
    }
    return cast(dict[str, Any], value)


def _routes() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "API_ROUTE_AUTHORITY.json"))
    value.update(authority_version="1.7.0", core_baseline=CORE, decision_id=DECISION_ID, approval_status="APPROVED_LOCAL")
    routes = value.get("routes")
    reserved = value.get("reserved_routes")
    if not isinstance(routes, list) or not isinstance(reserved, list):
        raise G8SuccessorError("route sections invalid")
    activated_ids = {row[0] for row in _ACTIVATED}
    remaining = []
    for item in reserved:
        if not isinstance(item, dict):
            continue
        if item.get("route_id") in activated_ids:
            continue
        if item.get("route_id") in _REMAINING_RESERVED:
            item["implementation_status"] = "RESERVED_G8_NOT_EXPOSED"
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
                "module": "tpaa_api.gui_co_attack",
                "dto_authority": "CROSS_LAYER_DTO_CONTRACTS",
                "route_id": logical,
                "gui_permission_id": gui_permission,
                "implementation_status": "IMPLEMENTED_G8",
            }
        )
    return cast(dict[str, Any], value)


def _route_security() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json"))
    active = value.get("active_routes")
    if not isinstance(active, list) or len(active) != 101:
        raise G8SuccessorError("G7 security route count must be 101")
    for index, row in enumerate(_ACTIVATED, start=102):
        logical, method, path, handler, _operation, _response, permission, gui_permission = row
        active.append(
            {
                "route_id": f"api.route.{index:03d}",
                "method": method,
                "path": path,
                "module": "tpaa_api.gui_co_attack",
                "handler": handler,
                "authorization_mode": "BUSINESS_AND_GUI_PERMISSION",
                "permission_id": permission,
                "gui_permission_id": gui_permission,
                "audit_mode": "ALWAYS",
                "audit_event": f"{logical}.read",
                "implementation_status": "IMPLEMENTED_G8",
            }
        )
    value.update(
        authority_version="1.6.0",
        core_baseline=CORE,
        parent_core_baseline="CB-1.12.0",
        decision_id=DECISION_ID,
        approval_id=APPROVAL_ID,
        approval_status="APPROVED_LOCAL",
        activation_status="ACTIVE",
        release_claim=False,
    )
    value["mapping_basis"] = {
        "route_graph_source": "CB-1.12.0 plus one implemented G8 co-attack route",
        "route_count": 102,
        "stable_id_rule": "Preserve api.route.001-101; append G8 deterministically.",
    }
    return cast(dict[str, Any], value)


def _g8_authority() -> dict[str, Any]:
    return {
        "authority_id": "GUI_CO_ATTACK_AUTHORITY",
        "authority_version": "1.0.0",
        "core_baseline": CORE,
        "parent_core_baseline": "CB-1.12.0",
        "decision_id": DECISION_ID,
        "approval_id": APPROVAL_ID,
        "activation_status": "ACTIVE",
        "rules": {
            "cluster_scope": "EXACT_CLUSTER_RELATION_ONLY",
            "cross_batch_cluster": "FORBIDDEN",
            "bvr_only": True,
            "strike_cluster_rejected": "FAIL_CLOSED",
            "missing_context": "HONEST_EMPTY_FORMATION",
            "no_total_score": True,
            "latest_fallback": "FORBIDDEN",
            "gui_business_recomputation": "FORBIDDEN",
            "browser_business_storage": "FORBIDDEN",
        },
        "single_owner_rules": {
            "co_attack_analysis_query": "tpaa_application.co_attack",
            "attack_cluster_resolver": "tpaa_application.weapon_event",
            "force_formation_context": "tpaa_application.batch_import",
            "gui_business_recomputation": "FORBIDDEN",
            "browser_business_storage": "FORBIDDEN",
        },
        "database": {
            "schema": "1.10.0",
            "migration_required": False,
            "reason": "Co-attack analysis is an exact cluster read model over existing Cluster/WE/Context relations; no new physical tables.",
        },
        "release_claim": False,
    }


def _metadata(filename: str) -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / filename))
    value.update(
        core_baseline=CORE,
        parent_core_baseline="CB-1.12.0",
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
        authority_version="1.6.0",
        core_baseline=CORE,
        decision_id=DECISION_ID,
        approval_status="APPROVED",
        approval_date="2026-11-07",
        approval_basis="G8 local successor inherits unchanged CB-1.12.0 artifacts; no DB schema change.",
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
        "SCHEMA_COMPATIBILITY_AUTHORITY.json": _schema_compatibility(),
        "GUI_CO_ATTACK_AUTHORITY.json": _g8_authority(),
        "G8_CO_ATTACK_APPROVAL.json": {
            "schema": "TPAA_G8_CO_ATTACK_APPROVAL_V1",
            "approval_id": APPROVAL_ID,
            "decision_id": DECISION_ID,
            "status": "APPROVED_LOCAL",
            "activation_status": "ACTIVE",
            "approved_core_baseline": CORE,
            "approved_at": "2026-11-07T00:00:00+08:00",
            "approver": "PROJECT_OWNER_G8_IMPLEMENTATION_DIRECTIVE",
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
                "rebaseline": "R3.8_G8_CO_ATTACK",
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
            "record_type": "G8_SUCCESSOR_IMPORT_PROVENANCE",
            "authority": False,
            "decision_id": DECISION_ID,
            "source_baseline": "CB-1.12.0",
            "source_baseline_lock_sha256": _sha256(PARENT / "BASELINE_LOCK.json"),
            "core_baseline": CORE,
            "db_schema_target": "1.10.0",
            "controlled_artifact_count": len(artifacts),
            "release_claim": False,
        },
    )
    (output / "README.md").write_text(
        "# CB-1.13.0 G8 Co-attack-analysis successor baseline\n\n"
        f"Decision: `{DECISION_ID}`. CB-1.12.0 remains the immutable parent. "
        "This local successor activates only the V24 co-attack analysis read route and does not authorize push or deployment.\n",
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
        raise G8SuccessorError(f"successor missing: {TARGET}")
    with tempfile.TemporaryDirectory(prefix="tpaa-g8-successor-") as temporary:
        expected = Path(temporary) / CORE
        build_successor(expected)
        expected_digest = _digest(expected)
    actual = _digest(TARGET)
    if actual != expected_digest:
        raise G8SuccessorError(f"successor drift: {actual} != {expected_digest}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        check_successor() if args.check else build_successor(TARGET)
        print(f"G8_SUCCESSOR_PASS core={CORE} digest={_digest(TARGET)}")
    except (OSError, ValueError, KeyError, G8SuccessorError) as exc:
        print(f"G8_SUCCESSOR_FAIL {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
