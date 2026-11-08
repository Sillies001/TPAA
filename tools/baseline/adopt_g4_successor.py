#!/usr/bin/env python3
"""Build or verify the local G4 CB-1.9.0 Batch-import successor baseline."""

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
PARENT = ROOT / "baseline" / "CB-1.8.0"
TARGET = ROOT / "baseline" / "CB-1.9.0"
CORE = "CB-1.9.0"
DECISION_ID = "G4-V33-BATCH-IMPORT-2026-11-06"
APPROVAL_ID = "G4-CB-1.9.0-LOCAL-IMPLEMENTATION-2026-11-06"


class G4SuccessorError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G4SuccessorError(f"expected JSON object: {path}")
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


def _field(name: str, transport: str, required: bool = True) -> dict[str, Any]:
    return {
        "field": name,
        "source": f"g4.{name}",
        "required": required,
        "transport_type": transport,
    }


_ACTIVATED = (
    ("gui.batches", "GET", "/api/v1/gui/batches", "list_batches", "listGuiBatches", "BatchListDTO", "DERIVED_DATA_READ", "batch.read"),
    ("gui.batch.detail", "GET", "/api/v1/gui/batches/{batch_id}", "batch_detail", "getGuiBatch", "BatchRegistrationDTO", "DERIVED_DATA_READ", "batch.read"),
    ("gui.batch.register", "POST", "/api/v1/gui/batches", "register_batch", "registerGuiBatch", "BatchRegistrationDTO", "SOURCE_IMPORT", "batch.register"),
    ("gui.batch.training_type", "POST", "/api/v1/gui/batches/{batch_id}/training-type-revisions", "revise_training_type", "reviseGuiBatchTrainingType", "BatchRegistrationDTO", "CONFIGURATION_WRITE", "batch.training_type.revise"),
    ("gui.context", "GET", "/api/v1/gui/contexts/{context_id}/force-formation", "get_context", "getGuiForceFormationContext", "ForceFormationContextDTO", "DERIVED_DATA_READ", "context.force_formation.read"),
    ("gui.context.revise", "POST", "/api/v1/gui/contexts/{context_id}/force-formation-revisions", "revise_context", "reviseGuiForceFormationContext", "ForceFormationContextDTO", "CONFIGURATION_WRITE", "context.force_formation.revise"),
)
_TICKET = (
    "gui.import.ticket",
    "POST",
    "/api/v1/gui/import-tickets",
    "issue_ticket",
    "issueGuiImportTicket",
    "ImportTicketDTO",
    "SOURCE_IMPORT",
    "batch.register",
)


def _dto() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "CROSS_LAYER_DTO_CONTRACTS.json"))
    value.update(core_baseline=CORE, authority_version="1.3.0", decision_id=DECISION_ID)
    contracts = value.get("contracts")
    if not isinstance(contracts, dict):
        raise G4SuccessorError("DTO contracts missing")
    common = [_field("schema", "string"), _field("provenance", "object")]
    contracts.update(
        {
            "ImportTicketDTO": {"fields": common + [_field("ticket_id", "string"), _field("kind", "string"), _field("entry_count", "integer"), _field("size_bytes", "integer"), _field("manifest_sha256", "string"), _field("expires_at", "string")]},
            "BatchRegistrationDTO": {"fields": common + [_field("batch_id", "uuid-string"), _field("session_id", "uuid-string"), _field("batch_date", "string"), _field("batch_training_type", "string"), _field("training_type_confirmed", "boolean"), _field("qualification_status", "string"), _field("source_manifest_sha256", "string"), _field("revision_no", "integer"), _field("reason_code", "string?", False), _field("v01_eligible", "boolean")]},
            "BatchListDTO": {"fields": common + [_field("items", "object"), _field("total_count", "integer")]},
            "ForceFormationContextDTO": {"fields": common + [_field("context_revision_id", "uuid-string"), _field("context_id", "uuid-string"), _field("revision_no", "integer"), _field("valid_from_session_time_us", "decimal-string"), _field("valid_to_session_time_us", "decimal-string?", False), _field("members", "object")]},
            "BatchImportErrorDTO": {"fields": common + [_field("status", "string"), _field("code", "string"), _field("detail", "string")]},
        }
    )
    rules = value.setdefault("transport_rules", {})
    if not isinstance(rules, dict):
        raise G4SuccessorError("DTO rules invalid")
    rules["g4_batch_import"] = {
        "local_path": "FORBIDDEN",
        "training_type_default": "FORBIDDEN",
        "unconfirmed_value": "UNCLASSIFIED",
        "v01_admission_status": "QUALIFIED_ONLY",
        "session_time_us": "decimal-string",
    }
    return cast(dict[str, Any], value)


def _routes() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "API_ROUTE_AUTHORITY.json"))
    value.update(authority_version="1.3.0", core_baseline=CORE, decision_id=DECISION_ID, approval_status="APPROVED_LOCAL")
    routes = value.get("routes")
    reserved = value.get("reserved_routes")
    if not isinstance(routes, list) or not isinstance(reserved, list):
        raise G4SuccessorError("route sections invalid")
    activated_ids = {row[0] for row in _ACTIVATED}
    remaining = []
    for item in reserved:
        if not isinstance(item, dict):
            continue
        if item.get("route_id") in activated_ids:
            continue
        item["implementation_status"] = "RESERVED_G4_NOT_EXPOSED"
        remaining.append(item)
    value["reserved_routes"] = remaining
    for row in (*_ACTIVATED, _TICKET):
        logical, method, path, handler, operation, response, _permission, gui_permission = row
        routes.append(
            {
                "method": method,
                "path": path,
                "handler": handler,
                "operation_id": operation,
                "response_model": response,
                "module": "tpaa_api.gui_batch",
                "dto_authority": "CROSS_LAYER_DTO_CONTRACTS",
                "route_id": logical,
                "gui_permission_id": gui_permission,
                "implementation_status": "IMPLEMENTED_G4",
            }
        )
    return cast(dict[str, Any], value)


def _route_security() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json"))
    active = value.get("active_routes")
    if not isinstance(active, list) or len(active) != 89:
        raise G4SuccessorError("G3 security route count must be 89")
    for index, row in enumerate((*_ACTIVATED, _TICKET), start=90):
        logical, method, path, handler, _operation, _response, permission, gui_permission = row
        active.append(
            {
                "route_id": f"api.route.{index:03d}",
                "method": method,
                "path": path,
                "module": "tpaa_api.gui_batch",
                "handler": handler,
                "authorization_mode": "BUSINESS_AND_GUI_PERMISSION",
                "permission_id": permission,
                "gui_permission_id": gui_permission,
                "audit_mode": "ALWAYS",
                "audit_event": f"{logical}.{'read' if method == 'GET' else 'mutation'}",
                "implementation_status": "IMPLEMENTED_G4",
            }
        )
    value.update(
        authority_version="1.2.0",
        core_baseline=CORE,
        parent_core_baseline="CB-1.8.0",
        decision_id=DECISION_ID,
        approval_id=APPROVAL_ID,
        approval_status="APPROVED_LOCAL",
        activation_status="ACTIVE",
        release_claim=False,
    )
    value["mapping_basis"] = {
        "route_graph_source": "CB-1.8.0 plus seven implemented G4 Batch/context routes",
        "route_count": 96,
        "stable_id_rule": "Preserve api.route.001-089; append G4 deterministically.",
    }
    return cast(dict[str, Any], value)


def _g4_authority() -> dict[str, Any]:
    return {
        "authority_id": "GUI_BATCH_IMPORT_AUTHORITY",
        "authority_version": "1.0.0",
        "core_baseline": CORE,
        "parent_core_baseline": "CB-1.8.0",
        "decision_id": DECISION_ID,
        "approval_id": APPROVAL_ID,
        "activation_status": "ACTIVE",
        "training_types": ["SIMPLE_OPPOSITION", "MIXED_OPPOSITION", "COMPREHENSIVE_OPPOSITION", "UNCLASSIFIED"],
        "qualification_states": ["PENDING_CONFIRMATION", "PARSING", "QUALIFIED", "FAILED"],
        "state_transitions": {
            "PENDING_CONFIRMATION": ["PARSING"],
            "PARSING": ["QUALIFIED", "FAILED"],
            "FAILED": ["PARSING"],
            "QUALIFIED": [],
        },
        "rules": {
            "training_type_explicit_confirmation": True,
            "default_training_type_forbidden": True,
            "unconfirmed_training_type": "UNCLASSIFIED",
            "stable_batch_id": "UUID5(actor,idempotency_key)",
            "ticket_storage": "PROCESS_MEMORY_ONLY",
            "ticket_ttl_seconds": 600,
            "ticket_max_bytes": 67108864,
            "local_path_exposure": "FORBIDDEN",
            "v01_admission": "QUALIFIED_ONLY",
            "failure_retry": "SAME_IDEMPOTENCY_KEY_AND_IMMUTABLE_MANIFEST",
            "training_type_revision": "AUDITED_APPEND_ONLY",
            "force_formation_revision": "AUDITED_EFFECTIVE_TIME_APPEND_ONLY",
        },
        "database": {
            "schema": "1.10.0",
            "migration_required": False,
            "reason": "G1 DB 1.10.0 already admitted all four G4 physical tables.",
        },
        "release_claim": False,
    }


def _metadata(filename: str) -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / filename))
    value.update(
        core_baseline=CORE,
        parent_core_baseline="CB-1.8.0",
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
        authority_version="1.2.0",
        core_baseline=CORE,
        decision_id=DECISION_ID,
        approval_status="APPROVED",
        approval_date="2026-11-06",
        approval_basis="G4 local successor inherits unchanged CB-1.6.0/G2/G3 artifacts explicitly.",
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
        "SCHEMA_COMPATIBILITY_AUTHORITY.json": _schema_compatibility(),
        "GUI_BATCH_IMPORT_AUTHORITY.json": _g4_authority(),
        "G4_BATCH_IMPORT_APPROVAL.json": {
            "schema": "TPAA_G4_BATCH_IMPORT_APPROVAL_V1",
            "approval_id": APPROVAL_ID,
            "decision_id": DECISION_ID,
            "status": "APPROVED_LOCAL",
            "activation_status": "ACTIVE",
            "approved_core_baseline": CORE,
            "approved_at": "2026-11-06T00:00:00+08:00",
            "approver": "PROJECT_OWNER_G4_IMPLEMENTATION_DIRECTIVE",
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
                "date": "2026-11-06",
                "rebaseline": "R3.6_G4_BATCH_IMPORT",
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
            "record_type": "G4_SUCCESSOR_IMPORT_PROVENANCE",
            "authority": False,
            "decision_id": DECISION_ID,
            "source_baseline": "CB-1.8.0",
            "source_baseline_lock_sha256": _sha256(PARENT / "BASELINE_LOCK.json"),
            "core_baseline": CORE,
            "db_schema_target": "1.10.0",
            "controlled_artifact_count": len(artifacts),
            "release_claim": False,
        },
    )
    (output / "README.md").write_text(
        "# CB-1.9.0 G4 Batch import successor baseline\n\n"
        f"Decision: `{DECISION_ID}`. CB-1.8.0 remains the immutable parent. "
        "This local successor activates only G4 Batch/context capabilities and does not authorize push or deployment.\n",
        encoding="utf-8",
    )


def check_successor() -> None:
    if not TARGET.is_dir():
        raise G4SuccessorError(f"successor missing: {TARGET}")
    with tempfile.TemporaryDirectory(prefix="tpaa-g4-successor-") as temporary:
        expected = Path(temporary) / CORE
        build_successor(expected)
        expected_digest = _digest(expected)
    actual = _digest(TARGET)
    if actual != expected_digest:
        raise G4SuccessorError(f"successor drift: {actual} != {expected_digest}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        check_successor() if args.check else build_successor(TARGET)
        print(f"G4_SUCCESSOR_PASS core={CORE} digest={_digest(TARGET)}")
    except (OSError, ValueError, KeyError, G4SuccessorError) as exc:
        print(f"G4_SUCCESSOR_FAIL {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
