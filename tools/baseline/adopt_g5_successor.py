#!/usr/bin/env python3
"""Build or verify the local G5 CB-1.10.0 Weapon-Event/Window/Perspective successor baseline."""

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
PARENT = ROOT / "baseline" / "CB-1.9.0"
TARGET = ROOT / "baseline" / "CB-1.10.0"
CORE = "CB-1.10.0"
DECISION_ID = "G5-V33-WEAPON-EVENT-2026-11-07"
APPROVAL_ID = "G5-CB-1.10.0-LOCAL-IMPLEMENTATION-2026-11-07"


class G5SuccessorError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G5SuccessorError(f"expected JSON object: {path}")
    return value


def _clone(value: object) -> Any:
    return json.loads(json.dumps(value))


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def _field(name: str, transport: str, required: bool = True, source: str | None = None) -> dict[str, Any]:
    return {
        "field": name,
        "source": source or f"g5.{name}",
        "required": required,
        "transport_type": transport,
    }


# G5 activates exactly the three pure Weapon-Event read-model routes. The V26 list
# (gui.batch.events), historical overview (gui.overview) and replay (gui.replay) stay
# reserved for G6/G7/G9 respectively.  Permission mapping mirrors
# GUI_PERMISSION_AUDIT_AUTHORITY: detail=DDR+weapon_event.read,
# window=RAW+weapon_event.window.read, perspective=DDR+weapon_event.perspective.read.
_ACTIVATED = (
    ("gui.event.detail", "GET", "/api/v1/gui/weapon-events/{weapon_event_id}", "weapon_event_detail", "getGuiWeaponEventDetail", "WeaponEventDetailDTO", "DERIVED_DATA_READ", "weapon_event.read"),
    ("gui.event.window", "GET", "/api/v1/gui/weapon-events/{weapon_event_id}/windows/{perspective}", "weapon_event_window", "getGuiWeaponEventWindow", "WeaponEventWindowDTO", "RAW_DATA_READ", "weapon_event.window.read"),
    ("gui.event.perspective", "GET", "/api/v1/gui/weapon-events/{weapon_event_id}/perspectives/{perspective}", "weapon_event_perspective", "getGuiWeaponEventPerspective", "WeaponEventPerspectiveDTO", "DERIVED_DATA_READ", "weapon_event.perspective.read"),
)
_REMAINING_RESERVED = ("gui.overview", "gui.batch.events", "gui.replay")


def _dto() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "CROSS_LAYER_DTO_CONTRACTS.json"))
    value.update(core_baseline=CORE, authority_version="1.4.0", decision_id=DECISION_ID)
    contracts = value.get("contracts")
    if not isinstance(contracts, dict):
        raise G5SuccessorError("DTO contracts missing")
    common = [_field("schema", "string"), _field("provenance", "object")]
    contracts.update(
        {
            "WeaponEventDetailDTO": {"fields": common + [
                _field("weapon_event_id", "uuid-string"),
                _field("batch_id", "uuid-string"),
                _field("release_id", "uuid-string?"),
                _field("category", "string"),
                _field("category_rule_version", "string"),
                _field("classification_exception", "boolean"),
                _field("shooter_entity_id", "uuid-string"),
                _field("target_entity_id", "uuid-string?", False),
                _field("episode_id", "uuid-string?"),
                _field("t1_session_time_us", "decimal-string"),
                _field("weapon_terminal_state", "string"),
                _field("adjudication_state", "string"),
                _field("observation_window_state", "string"),
                _field("cluster_id", "uuid-string?", False),
            ]},
            "WeaponEventWindowDTO": {"fields": common + [
                _field("weapon_event_id", "uuid-string"),
                _field("perspective", "string"),
                _field("resolver_version", "string"),
                _field("start_session_time_us", "decimal-string"),
                _field("end_session_time_us", "decimal-string?", False),
                _field("t0s_session_time_us", "decimal-string?", False),
                _field("t0t_session_time_us", "decimal-string?", False),
                _field("t1_session_time_us", "decimal-string"),
                _field("t2_session_time_us", "decimal-string?", False),
                _field("t3_session_time_us", "decimal-string?", False),
                _field("cue_session_time_us", "decimal-string?", False),
                _field("response_session_time_us", "decimal-string?", False),
                _field("j_session_time_us", "decimal-string?", False),
                _field("terminal_state", "string"),
                _field("adjudication_state", "string"),
                _field("window_state", "string"),
                _field("alignment_state", "string"),
                _field("coverage", "string"),
                _field("reason", "string?"),
            ]},
            "WeaponEventPerspectiveDTO": {"fields": common + [
                _field("weapon_event_id", "uuid-string"),
                _field("perspective", "string"),
                _field("projection_version", "string"),
                _field("allowed", "boolean"),
                _field("denial_reason", "string?"),
                _field("geometry_available", "boolean"),
                _field("series_available", "boolean"),
            ]},
            "UnavailableStateDTO": {"fields": common + [
                _field("status", "string"),
                _field("reason_code", "string"),
                _field("detail", "string"),
            ]},
        }
    )
    rules = value.setdefault("transport_rules", {})
    if not isinstance(rules, dict):
        raise G5SuccessorError("DTO rules invalid")
    rules["g5_weapon_event"] = {
        "session_time_us": "decimal-string",
        "latest_fallback": "FORBIDDEN",
        "gui_business_recomputation": "FORBIDDEN",
        "cross_batch_we_borrowing": "FORBIDDEN",
        "terminal_adjudication_window_states": "INDEPENDENT",
    }
    return cast(dict[str, Any], value)


def _routes() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "API_ROUTE_AUTHORITY.json"))
    value.update(authority_version="1.4.0", core_baseline=CORE, decision_id=DECISION_ID, approval_status="APPROVED_LOCAL")
    routes = value.get("routes")
    reserved = value.get("reserved_routes")
    if not isinstance(routes, list) or not isinstance(reserved, list):
        raise G5SuccessorError("route sections invalid")
    activated_ids = {row[0] for row in _ACTIVATED}
    remaining = []
    for item in reserved:
        if not isinstance(item, dict):
            continue
        if item.get("route_id") in activated_ids:
            continue
        if item.get("route_id") in _REMAINING_RESERVED:
            item["implementation_status"] = "RESERVED_G5_NOT_EXPOSED"
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
                "module": "tpaa_api.gui_weapon_event",
                "dto_authority": "CROSS_LAYER_DTO_CONTRACTS",
                "route_id": logical,
                "gui_permission_id": gui_permission,
                "implementation_status": "IMPLEMENTED_G5",
            }
        )
    return cast(dict[str, Any], value)


def _route_security() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json"))
    active = value.get("active_routes")
    if not isinstance(active, list) or len(active) != 96:
        raise G5SuccessorError("G4 security route count must be 96")
    for index, row in enumerate(_ACTIVATED, start=97):
        logical, method, path, handler, _operation, _response, permission, gui_permission = row
        active.append(
            {
                "route_id": f"api.route.{index:03d}",
                "method": method,
                "path": path,
                "module": "tpaa_api.gui_weapon_event",
                "handler": handler,
                "authorization_mode": "BUSINESS_AND_GUI_PERMISSION",
                "permission_id": permission,
                "gui_permission_id": gui_permission,
                "audit_mode": "ALWAYS",
                "audit_event": f"{logical}.read",
                "implementation_status": "IMPLEMENTED_G5",
            }
        )
    value.update(
        authority_version="1.3.0",
        core_baseline=CORE,
        parent_core_baseline="CB-1.9.0",
        decision_id=DECISION_ID,
        approval_id=APPROVAL_ID,
        approval_status="APPROVED_LOCAL",
        activation_status="ACTIVE",
        release_claim=False,
    )
    value["mapping_basis"] = {
        "route_graph_source": "CB-1.9.0 plus three implemented G5 Weapon-Event read-model routes",
        "route_count": 99,
        "stable_id_rule": "Preserve api.route.001-096; append G5 deterministically.",
    }
    return cast(dict[str, Any], value)


def _g5_authority() -> dict[str, Any]:
    return {
        "authority_id": "GUI_WEAPON_EVENT_AUTHORITY",
        "authority_version": "1.0.0",
        "core_baseline": CORE,
        "parent_core_baseline": "CB-1.9.0",
        "decision_id": DECISION_ID,
        "approval_id": APPROVAL_ID,
        "activation_status": "ACTIVE",
        "categories": ["WVR", "BVR", "STRIKE", "UNKNOWN"],
        "terminal_states": ["TERMINAL_KNOWN", "TERMINAL_UNKNOWN"],
        "adjudication_states": ["ADJUDICATED", "ADJUDICATION_PENDING"],
        "window_states": ["WINDOW_OPEN", "WINDOW_PARTIAL", "WINDOW_CLOSED"],
        "alignment_states": ["ALIGNED", "ALIGNMENT_UNRESOLVED"],
        "single_owner_rules": {
            "weapon_event_detector": "tpaa_application.weapon_event",
            "weapon_event_identity": "tpaa_application.weapon_event",
            "weapon_event_episode_linker": "tpaa_application.weapon_event",
            "weapon_category_resolver": "tpaa_application.weapon_event",
            "attack_cluster_resolver": "tpaa_application.weapon_event",
            "event_window_resolver": "tpaa_application.event_window",
            "perspective_projection": "tpaa_application.perspective",
            "gui_business_recomputation": "FORBIDDEN",
            "browser_business_storage": "FORBIDDEN",
        },
        "rules": {
            "we_cardinality": "ONE_PER_WEAPON_LAUNCH",
            "cluster_cardinality": "RELATION_ONLY_MULTIPLE_WE",
            "window_interval": "HALF_OPEN_START_INCLUSIVE",
            "window_overlap": "ALLOWED_WITHIN_EPISODE",
            "t2_unknown_semantics": "TERMINAL_UNKNOWN",
            "terminal_adjudication_window_independent": True,
            "historical_revision_reproducible": True,
            "exact_identity_no_latest_fallback": True,
            "cross_batch_we_borrowing": "FORBIDDEN",
            "cross_batch_ingress_rejection": "DETECTOR_IDENTITY_IMMEDIATE_AUDITED",
            "identity_supersession": "SOURCE_REVISION_YIELDS_NEW_UUID_SUPERSEDES_OLD_NO_INPLACE_MUTATION",
            "cluster_identity_stability": "UUID_FROM_SORTED_WE_ID_SET_ONLY",
            "dto_single_source": "CANONICAL_CONTRACT_GENERATES_PYTHON_AND_TYPESCRIPT",
            "capability_states": ["CAPABILITY_DISABLED", "ADAPTER_UNAVAILABLE", "EMPTY", "READY"],
            "http_404_semantics": "EXACT_WEAPON_EVENT_ABSENT_UNDER_READY_BACKEND",
        },
        # Activation honesty: do not declare ACTIVE what is not yet implemented.
        # ACTIVE = implemented and covered by the local G5 closure gates.
        "capability_status": {
            "we_detection_identity_linker_category_cluster": "ACTIVE",
            "event_window_resolver": "ACTIVE",
            "perspective_projection": "ACTIVE",
            "cross_batch_ingress_rejection": "ACTIVE",
            "identity_supersession": "ACTIVE",
            "four_state_read_model": "ACTIVE",
            "cluster_stability_and_query": "ACTIVE",
            "cross_batch_rejection_audit": "ACTIVE",
            "dto_single_source_generation": "ACTIVE",
            "trusted_capability_resolver": "ACTIVE",
            "exact_we_release_context_scope": "ACTIVE",
            "canonical_source_store_adapter": "ACTIVE",
            "api_routes_registration": "ACTIVE",
            "atomic_activation_rollback": "ACTIVE",
            "direct_api_negative_tests": "ACTIVE",
        },
        "database": {
            "schema": "1.10.0",
            "migration_required": False,
            "reason": "WE via existing Event subtype/relations; Cluster via existing Relation subtype; Window/Perspective are rebuildable non-persistent projections.",
        },
        "release_claim": False,
    }


def _metadata(filename: str) -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / filename))
    value.update(
        core_baseline=CORE,
        parent_core_baseline="CB-1.9.0",
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
        authority_version="1.3.0",
        core_baseline=CORE,
        decision_id=DECISION_ID,
        approval_status="APPROVED",
        approval_date="2026-11-07",
        approval_basis="G5 local successor inherits unchanged CB-1.9.0 artifacts explicitly; no DB schema change.",
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
        "SCHEMA_COMPATIBILITY_AUTHORITY.json": _schema_compatibility(),
        "GUI_WEAPON_EVENT_AUTHORITY.json": _g5_authority(),
        "G5_WEAPON_EVENT_APPROVAL.json": {
            "schema": "TPAA_G5_WEAPON_EVENT_APPROVAL_V1",
            "approval_id": APPROVAL_ID,
            "decision_id": DECISION_ID,
            "status": "APPROVED_LOCAL",
            "activation_status": "ACTIVE",
            "approved_core_baseline": CORE,
            "approved_at": "2026-11-07T00:00:00+08:00",
            "approver": "PROJECT_OWNER_G5_IMPLEMENTATION_DIRECTIVE",
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
                "rebaseline": "R3.6_G5_WEAPON_EVENT",
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
            "record_type": "G5_SUCCESSOR_IMPORT_PROVENANCE",
            "authority": False,
            "decision_id": DECISION_ID,
            "source_baseline": "CB-1.9.0",
            "source_baseline_lock_sha256": _sha256(PARENT / "BASELINE_LOCK.json"),
            "core_baseline": CORE,
            "db_schema_target": "1.10.0",
            "controlled_artifact_count": len(artifacts),
            "release_claim": False,
        },
    )
    (output / "README.md").write_text(
        "# CB-1.10.0 G5 Weapon-Event/Window/Perspective successor baseline\n\n"
        f"Decision: `{DECISION_ID}`. CB-1.9.0 remains the immutable parent. "
        "This local successor activates only the three G5 Weapon-Event read-model routes and does not authorize push or deployment.\n",
        encoding="utf-8",
    )


def check_successor() -> None:
    if not TARGET.is_dir():
        raise G5SuccessorError(f"successor missing: {TARGET}")
    with tempfile.TemporaryDirectory(prefix="tpaa-g5-successor-") as temporary:
        expected = Path(temporary) / CORE
        build_successor(expected)
        expected_digest = _digest(expected)
    actual = _digest(TARGET)
    if actual != expected_digest:
        raise G5SuccessorError(f"successor drift: {actual} != {expected_digest}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        check_successor() if args.check else build_successor(TARGET)
        print(f"G5_SUCCESSOR_PASS core={CORE} digest={_digest(TARGET)}")
    except (OSError, ValueError, KeyError, G5SuccessorError) as exc:
        print(f"G5_SUCCESSOR_FAIL {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
