#!/usr/bin/env python3
"""Build/check the additive G1 CB-1.6.0 successor without mutating CB-1.5.0."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "baseline" / "CB-1.5.0"
TARGET_ROOT = REPO_ROOT / "baseline" / "CB-1.6.0"
REGISTRY = REPO_ROOT / "docs" / "gui" / "demo-v33" / "V33_FINAL_VIEW_REGISTRY.json"
MATRIX = REPO_ROOT / "docs" / "compliance" / "GUI_V33_CONFORMANCE_MATRIX.json"
VERSION_DECISION = (
    REPO_ROOT / "docs" / "gui" / "demo-v33" / "G0R_VERSION_AND_COMPATIBILITY_DECISION.json"
)
OLD_CORE = "CB-1.5.0"
NEW_CORE = "CB-1.6.0"
DB_SCHEMA = "1.10.0"
DECISION_ID = "G1-V33-MACHINE-AUTHORITY-2026-11-06"
APPROVAL_DATE = "2026-11-06"


class G1SuccessorError(RuntimeError):
    """The deterministic G1 successor cannot be built or verified."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G1SuccessorError(f"expected JSON object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _field(name: str, sql_type: str, *, nullable: bool = False, tail: str = "") -> dict[str, Any]:
    null_sql = "NULL" if nullable else "NOT NULL"
    return {
        "name": name,
        "type": sql_type,
        "nullable": nullable,
        "sql": f"{name} {sql_type} {null_sql}{tail}",
    }


def _new_tables() -> dict[str, Any]:
    return {
        "registry.batch_registration": {
            "fields": [
                _field("batch_id", "uuid", tail=" PRIMARY KEY"),
                _field("session_id", "uuid", tail=" REFERENCES registry.training_session(session_id)"),
                _field("batch_date", "date"),
                _field("batch_training_type", "text", tail=" CHECK (batch_training_type IN ('SIMPLE_OPPOSITION','MIXED_OPPOSITION','COMPREHENSIVE_OPPOSITION','UNCLASSIFIED'))"),
                _field("training_type_confirmed", "boolean", tail=" DEFAULT false"),
                _field("context_id", "uuid", nullable=True),
                _field("release_id", "uuid", nullable=True),
                _field("qualification_status", "text"),
                _field("source_manifest_sha256", "char(64)"),
                _field("revision_no", "integer", tail=" CHECK (revision_no >= 1)"),
                _field("created_by", "text"),
                _field("created_at", "timestamptz", tail=" DEFAULT now()"),
            ],
            "constraints": ["UNIQUE (session_id, batch_id)", "UNIQUE (batch_id, revision_no)"],
            "source": "G1 v33 capability admission: persistent Batch Registration",
            "schema_version": DB_SCHEMA,
        },
        "registry.batch_training_type_revision": {
            "fields": [
                _field("revision_id", "uuid", tail=" PRIMARY KEY"),
                _field("batch_id", "uuid", tail=" REFERENCES registry.batch_registration(batch_id)"),
                _field("revision_no", "integer", tail=" CHECK (revision_no >= 1)"),
                _field("old_training_type", "text", nullable=True),
                _field("new_training_type", "text"),
                _field("reason", "text"),
                _field("changed_by", "text"),
                _field("changed_at", "timestamptz", tail=" DEFAULT now()"),
            ],
            "constraints": ["UNIQUE (batch_id, revision_no)"],
            "source": "G1 v33 capability admission: audited training type revision",
            "schema_version": DB_SCHEMA,
        },
        "context.force_formation_context_revision": {
            "fields": [
                _field("context_revision_id", "uuid", tail=" PRIMARY KEY"),
                _field("context_id", "uuid"),
                _field("revision_no", "integer", tail=" CHECK (revision_no >= 1)"),
                _field("valid_from_session_time_us", "bigint"),
                _field("valid_to_session_time_us", "bigint", nullable=True),
                _field("source", "text"),
                _field("reason", "text"),
                _field("changed_by", "text"),
                _field("created_at", "timestamptz", tail=" DEFAULT now()"),
            ],
            "constraints": ["UNIQUE (context_id, revision_no)"],
            "source": "G1 v33 capability admission: effective-time force/formation context",
            "schema_version": DB_SCHEMA,
        },
        "context.force_formation_member": {
            "fields": [
                _field("context_revision_id", "uuid", tail=" REFERENCES context.force_formation_context_revision(context_revision_id)"),
                _field("aircraft_id", "uuid"),
                _field("formation_id", "text", nullable=True),
                _field("side", "text", tail=" CHECK (side IN ('RED','BLUE','NEUTRAL','UNASSIGNED','CONFLICT'))"),
                _field("member_role", "text"),
                _field("independent_target", "boolean", tail=" DEFAULT false"),
            ],
            "constraints": ["PRIMARY KEY (context_revision_id, aircraft_id)"],
            "source": "G1 v33 capability admission: normalized formation membership",
            "schema_version": DB_SCHEMA,
        },
    }


def _dto_field(name: str, transport: str, required: bool = True) -> dict[str, Any]:
    return {"field": name, "source": f"g1.{name}", "required": required, "transport_type": transport}


def _dto_contracts() -> dict[str, Any]:
    common = [_dto_field("schema", "string"), _dto_field("reason_code", "string", False)]
    definitions: dict[str, list[dict[str, Any]]] = {
        "GuiCatalogDTO": common + [_dto_field("views", "object"), _dto_field("features", "object")],
        "GuiBootstrapDTO": common + [_dto_field("catalog", "object"), _dto_field("principal", "object")],
        "GuiSelectorDTO": common + [_dto_field("selector_id", "string"), _dto_field("items", "object")],
        "HistoricalTrainingOverviewDTO": common + [_dto_field("query_context_id", "uuid-string"), _dto_field("batch_ids", "array[string]"), _dto_field("payload", "object")],
        "BatchOverviewSummaryDTO": common + [_dto_field("batch_id", "uuid-string"), _dto_field("release_id", "uuid-string?"), _dto_field("available_for_v26", "boolean")],
        "BatchListItemDTO": common + [_dto_field("batch_id", "uuid-string"), _dto_field("batch_training_type", "string"), _dto_field("qualification_status", "string")],
        "TaskMetricTrendDTO": common + [_dto_field("metric_id", "string"), _dto_field("definition_version", "string"), _dto_field("points", "object")],
        "EquipmentMetricTrendDTO": common + [_dto_field("metric_id", "string"), _dto_field("unit", "string"), _dto_field("comparability", "object")],
        "BatchEventSummaryDTO": common + [_dto_field("batch_id", "uuid-string"), _dto_field("weapon_event_count", "integer"), _dto_field("cluster_count", "integer")],
        "WeaponEventListItemDTO": common + [_dto_field("weapon_event_id", "uuid-string"), _dto_field("revision_no", "integer"), _dto_field("cluster_id", "uuid-string?"), _dto_field("category", "string")],
        "WeaponEventDetailDTO": common + [_dto_field("weapon_event_id", "uuid-string"), _dto_field("revision_no", "integer"), _dto_field("provenance", "object")],
        "WeaponEventPerspectiveDTO": common + [_dto_field("weapon_event_id", "uuid-string"), _dto_field("perspective", "string"), _dto_field("scope", "string"), _dto_field("projection", "object")],
        "WeaponEventWindowDTO": common + [_dto_field("weapon_event_id", "uuid-string"), _dto_field("perspective", "string"), _dto_field("resolver_version", "string"), _dto_field("window", "object")],
        "EpisodeEventRelationDTO": common + [_dto_field("episode_id", "uuid-string"), _dto_field("weapon_event_id", "uuid-string"), _dto_field("relation", "object")],
        "TargetDebriefProjectionDTO": common + [_dto_field("weapon_event_id", "uuid-string"), _dto_field("geometry", "object"), _dto_field("cues", "object"), _dto_field("responses", "object"), _dto_field("series", "object"), _dto_field("outcome", "object")],
        "BatchRegistrationDTO": common + [_dto_field("batch_id", "uuid-string"), _dto_field("batch_date", "string"), _dto_field("batch_training_type", "string"), _dto_field("revision_no", "integer")],
        "BatchTrainingTypeRevisionDTO": common + [_dto_field("revision_id", "uuid-string"), _dto_field("batch_id", "uuid-string"), _dto_field("old_value", "string?"), _dto_field("new_value", "string")],
        "ForceFormationContextDTO": common + [_dto_field("context_revision_id", "uuid-string"), _dto_field("members", "object")],
        "ContextRevisionDTO": common + [_dto_field("context_id", "uuid-string"), _dto_field("revision_no", "integer"), _dto_field("valid_from_session_time_us", "decimal-string")],
        "ReplayContextDTO": common + [_dto_field("release_id", "uuid-string"), _dto_field("context_id", "uuid-string"), _dto_field("ranges", "object")],
        "SeriesRangeDTO": common + [_dto_field("parameter", "string"), _dto_field("unit", "string"), _dto_field("time_base", "string"), _dto_field("points", "object")],
        "MediaManifestDTO": common + [_dto_field("release_id", "uuid-string"), _dto_field("items", "object")],
        "UnavailableStateDTO": common + [_dto_field("status", "string"), _dto_field("coverage", "number?"), _dto_field("provenance", "object")],
    }
    return {name: {"fields": fields} for name, fields in definitions.items()}


def _reserved_routes() -> list[dict[str, Any]]:
    specs = (
        ("gui.catalog", "GET", "/api/v1/gui/catalog", "gui.view"),
        ("gui.bootstrap", "GET", "/api/v1/gui/bootstrap", "gui.view"),
        ("gui.overview", "GET", "/api/v1/gui/historical-overview", "batch.history.read"),
        ("gui.batches", "GET", "/api/v1/gui/batches", "batch.read"),
        ("gui.batch.detail", "GET", "/api/v1/gui/batches/{batch_id}", "batch.read"),
        ("gui.batch.register", "POST", "/api/v1/gui/batches", "batch.register"),
        ("gui.batch.training_type", "POST", "/api/v1/gui/batches/{batch_id}/training-type-revisions", "batch.training_type.revise"),
        ("gui.batch.events", "GET", "/api/v1/gui/batches/{batch_id}/weapon-events", "weapon_event.read"),
        ("gui.event.detail", "GET", "/api/v1/gui/weapon-events/{weapon_event_id}", "weapon_event.read"),
        ("gui.event.perspective", "GET", "/api/v1/gui/weapon-events/{weapon_event_id}/perspectives/{perspective}", "weapon_event.perspective.read"),
        ("gui.event.window", "GET", "/api/v1/gui/weapon-events/{weapon_event_id}/windows/{perspective}", "weapon_event.window.read"),
        ("gui.context", "GET", "/api/v1/gui/contexts/{context_id}/force-formation", "context.force_formation.read"),
        ("gui.context.revise", "POST", "/api/v1/gui/contexts/{context_id}/force-formation-revisions", "context.force_formation.revise"),
        ("gui.replay", "GET", "/api/v1/gui/weapon-events/{weapon_event_id}/replay-context", "replay.read"),
    )
    return [
        {
            "route_id": route_id,
            "method": method,
            "path": path,
            "permission_id": permission,
            "audit_event": f"{route_id}.{'read' if method == 'GET' else 'mutation'}",
            "dto_authority": "CROSS_LAYER_DTO_CONTRACTS",
            "implementation_status": "RESERVED_G1_NOT_EXPOSED",
            "profile_exposure": ["DESKTOP", "SERVICE"],
        }
        for route_id, method, path, permission in specs
    ]


def _admission_authority() -> dict[str, Any]:
    return {
        "authority_id": "GUI_DOMAIN_ADMISSION_AUTHORITY",
        "authority_version": "1.0.0",
        "core_baseline": NEW_CORE,
        "decision_id": DECISION_ID,
        "approval_status": "APPROVED_LOCAL",
        "decisions": [
            {"concept": "BatchWorkset", "lifecycle": "APPLICATION_READ_SCOPE", "persistent": False},
            {"concept": "BatchRegistration/BatchMetadata", "lifecycle": "AUDITED_REVISIONED", "persistent": True},
            {"concept": "WeaponEvent", "lifecycle": "EXISTING_EVENT_SUBTYPE_AND_RELATIONS", "persistent": "VIA_EXISTING_EVENT"},
            {"concept": "AttackCluster", "lifecycle": "EXISTING_RELATION_SUBTYPE", "persistent": "VIA_EXISTING_RELATION"},
            {"concept": "EventWindowProjection", "lifecycle": "REBUILDABLE_VERSIONED_PROJECTION", "persistent": False},
            {"concept": "PerspectiveProjection", "lifecycle": "REBUILDABLE_AUTHORIZED_READ_MODEL", "persistent": False},
            {"concept": "Force/Formation Context", "lifecycle": "AUDITED_EFFECTIVE_TIME_REVISION", "persistent": True},
            {"concept": "HistoricalOverview", "lifecycle": "EXACT_BATCH_SET_READ_MODEL", "persistent": False},
            {"concept": "TaskMetricDefinition", "lifecycle": "SEPARATE_METRIC_ADMISSION", "persistent": False},
        ],
        "single_owner_rules": {
            "weapon_event_detector": "Application Weapon Event owner",
            "window_resolver": "Application Event Window owner",
            "gui_business_recomputation": "FORBIDDEN",
            "browser_business_storage": "FORBIDDEN",
        },
    }


def _permission_authority() -> dict[str, Any]:
    permissions = sorted({route["permission_id"] for route in _reserved_routes()})
    return {
        "authority_id": "GUI_PERMISSION_AUDIT_AUTHORITY",
        "authority_version": "1.0.0",
        "core_baseline": NEW_CORE,
        "decision_id": DECISION_ID,
        "approval_status": "APPROVED",
        "permissions": [{"permission_id": item, "unknown_policy": "DENY"} for item in permissions],
        "audit_policy": {
            "mutations": "ALWAYS",
            "sensitive_reads": "ALWAYS",
            "forbidden_fields": ["authorization", "bearer", "desktop_nonce", "absolute_path"],
        },
    }


def _state_reason_authority() -> dict[str, Any]:
    return {
        "authority_id": "GUI_STATE_REASON_AUTHORITY",
        "authority_version": "1.0.0",
        "core_baseline": NEW_CORE,
        "states": ["LOADING", "EMPTY", "READY", "DEGRADED", "ERROR", "FORBIDDEN", "N_A"],
        "reasons": [
            "EXACT_CONTEXT_REQUIRED", "EXACT_BATCH_REQUIRED", "NOT_AUTHORIZED", "NOT_APPLICABLE",
            "NO_QUALIFIED_DATA", "PROJECTION_UNAVAILABLE", "WINDOW_PARTIAL", "ALIGNMENT_UNRESOLVED",
            "SCHEMATIC_ONLY", "BACKEND_UNAVAILABLE", "SYSTEM_ERROR"
        ],
        "unknown_reason_policy": "SYSTEM_ERROR_FAIL_CLOSED",
    }


def _metric_authority() -> dict[str, Any]:
    return {
        "authority_id": "GUI_TASK_METRIC_ADMISSION_AUTHORITY",
        "authority_version": "1.0.0",
        "core_baseline": NEW_CORE,
        "approval_status": "NOT_ADMITTED",
        "candidates": ["KILL_RATIO", "EXCHANGE_RATIO", "MISSION_COMPLETION_RATE"],
        "rule": "No candidate may be computed or displayed as authoritative before independent Metric Definition admission.",
    }


def _view_authority() -> dict[str, Any]:
    registry = _load(REGISTRY)
    matrix = _load(MATRIX)
    matrix_by_id = {item["id"]: item for item in matrix["views"]}
    views = []
    for item in registry["views"]:
        details = matrix_by_id[item["id"]]
        predecessor = ["V08"] if item["id"] == "V24" else []
        return_target = "V08" if item["id"] == "V24" else None
        views.append(
            {
                "view_id": item["id"],
                "title": item["title"],
                "module": item["module"],
                "entry_type": item["entry"],
                "required_context": ["release_id", "context_id"] + (["batch_id"] if item["id"] in {"V01", "V26"} else []),
                "allowed_predecessor": predecessor,
                "return_target": return_target,
                "p_capabilities": details["p_mapping"],
                "query_route_ids": [],
                "mutation_route_ids": [],
                "required_permissions": [],
                "feature_gates": ["TPAA_GUI_SHELL=WEBENGINE_V33"],
                "states": ["LOADING", "EMPTY", "READY", "DEGRADED", "ERROR", "FORBIDDEN", "N_A"],
                "perspectives": item["perspectives"],
                "visual_baseline_id": "GUI-DEMO-V33-2026-11-05",
            }
        )
    return {
        "authority_id": "GUI_VIEW_CONTRACT",
        "authority_version": "1.0.0-v33",
        "core_baseline": NEW_CORE,
        "baseline_id": "GUI-DEMO-V33-2026-11-05",
        "source_hashes": {"registry": _sha256(REGISTRY), "matrix": _sha256(MATRIX)},
        "views": views,
    }


def _update_core(canonical: Path) -> None:
    path = canonical / "CORE_LOGICAL_MODEL.json"
    core = _load(path)
    core["core_baseline"] = NEW_CORE
    core["engineering_baseline"] = "ED-2.1"
    core["db_schema_version"] = DB_SCHEMA
    tables = core.get("tables")
    if not isinstance(tables, dict):
        raise G1SuccessorError("CORE_LOGICAL_MODEL tables invalid")
    for table in tables.values():
        if isinstance(table, dict):
            table["schema_version"] = DB_SCHEMA
    tables.update(_new_tables())
    _write(path, core)


def _update_dto(canonical: Path) -> None:
    path = canonical / "CROSS_LAYER_DTO_CONTRACTS.json"
    dto = _load(path)
    dto["core_baseline"] = NEW_CORE
    contracts = dto.get("contracts")
    if not isinstance(contracts, dict):
        raise G1SuccessorError("DTO contracts invalid")
    overlap = set(contracts) & set(_dto_contracts())
    if overlap:
        raise G1SuccessorError(f"DTO contract collision: {sorted(overlap)}")
    contracts.update(_dto_contracts())
    _write(path, dto)


def _update_routes(canonical: Path) -> None:
    path = canonical / "API_ROUTE_AUTHORITY.json"
    authority = _load(path)
    authority.update(
        {
            "authority_version": "1.1.0",
            "core_baseline": NEW_CORE,
            "decision_id": DECISION_ID,
            "scope": authority["scope"] + " G1 reserved GUI routes are not exposed until implemented.",
            "reserved_routes": _reserved_routes(),
        }
    )
    _write(path, authority)


def _update_rules(canonical: Path) -> None:
    path = canonical / "CORE_RULES.json"
    authority = _load(path)
    authority["core_baseline"] = NEW_CORE
    authority["version"] = "1.1.0"
    rules = authority.get("rules")
    if not isinstance(rules, list):
        raise G1SuccessorError("CORE_RULES rules invalid")
    rules.extend(
        [
            {"id": "CR-GUI-001", "name": "Exact Batch Context", "rule": "V01/V26 and every aggregate bind an exact Batch set; latest/current fallback is forbidden."},
            {"id": "CR-GUI-002", "name": "Single Weapon Event Owner", "rule": "GUI and metric plugins consume the authoritative Event/Relation projection and never redetect weapon events."},
            {"id": "CR-GUI-003", "name": "Perspective Fail Closed", "rule": "Missing target-side evidence stays unavailable and may not be filled from W or shooter evidence."},
            {"id": "CR-GUI-004", "name": "No Browser Business Truth", "rule": "Browser storage and browser calculation are forbidden as authorities for context, permissions, metrics, adjudication or results."},
        ]
    )
    _write(path, authority)


def _update_indexes(canonical: Path) -> None:
    path = canonical / "PHYSICAL_INDEX_AUTHORITY.json"
    authority = _load(path)
    authority.update({"authority_version": "1.1.0", "core_baseline": NEW_CORE, "db_schema_version": DB_SCHEMA, "decision_id": DECISION_ID})
    indexes = authority.get("indexes")
    if not isinstance(indexes, list):
        raise G1SuccessorError("PHYSICAL_INDEX_AUTHORITY indexes invalid")
    indexes.extend(
        [
            {"index_id": "registry.batch_registration.batch_id.PRIMARY_KEY", "table": "registry.batch_registration", "fields": ["batch_id"], "kind": "PRIMARY_KEY", "source_sql": "batch_id uuid PRIMARY KEY", "derivation": "CORE_LOGICAL_MODEL"},
            {"index_id": "registry.batch_training_type_revision.batch_revision.UNIQUE", "table": "registry.batch_training_type_revision", "fields": ["batch_id", "revision_no"], "kind": "UNIQUE", "source_sql": "UNIQUE (batch_id, revision_no)", "derivation": "CORE_LOGICAL_MODEL"},
            {"index_id": "context.force_formation_context_revision.context_revision.UNIQUE", "table": "context.force_formation_context_revision", "fields": ["context_id", "revision_no"], "kind": "UNIQUE", "source_sql": "UNIQUE (context_id, revision_no)", "derivation": "CORE_LOGICAL_MODEL"},
            {"index_id": "context.force_formation_member.revision_aircraft.PRIMARY_KEY", "table": "context.force_formation_member", "fields": ["context_revision_id", "aircraft_id"], "kind": "PRIMARY_KEY", "source_sql": "PRIMARY KEY (context_revision_id, aircraft_id)", "derivation": "CORE_LOGICAL_MODEL"},
        ]
    )
    _write(path, authority)


def _compatibility(canonical: Path) -> None:
    inherited = []
    for path in sorted(canonical.glob("*.json"), key=lambda item: item.name):
        value = _load(path)
        core = value.get("core_baseline")
        if isinstance(core, str) and core != NEW_CORE:
            inherited.append({"file": path.name, "declared_core_baseline": core, "compatible_core_baseline": NEW_CORE, "approval_status": "APPROVED"})
    authority = {
        "authority_id": "SCHEMA_COMPATIBILITY_AUTHORITY",
        "authority_version": "1.1.0",
        "core_baseline": NEW_CORE,
        "current_db_schema": DB_SCHEMA,
        "decision_id": DECISION_ID,
        "approval_status": "APPROVED",
        "approval_date": APPROVAL_DATE,
        "approval_basis": "G1 v33 additive successor; CB-1.5.0 remains immutable direct parent.",
        "compatibility_policy": "API v1 additive; schema 1.10.0 requires governed migration and non-empty downgrade refusal.",
        "core_inheritance": inherited,
        "entries": [{"schema_version": value, "compatible_core_baseline": NEW_CORE, "status": "HISTORICAL_READABLE" if value != DB_SCHEMA else "CURRENT"} for value in ("1.6.0", "1.7.0", "1.8.0", "1.9.0", DB_SCHEMA)],
    }
    _write(canonical / "SCHEMA_COMPATIBILITY_AUTHORITY.json", authority)


def _directory_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def build_successor(destination: Path) -> None:
    if destination.exists():
        raise G1SuccessorError(f"destination already exists: {destination}")
    predecessor_hash = _sha256(SOURCE_ROOT / "BASELINE_LOCK.json")
    shutil.copytree(SOURCE_ROOT, destination)
    canonical = destination / "canonical"
    _update_core(canonical)
    _update_dto(canonical)
    _update_routes(canonical)
    _update_rules(canonical)
    _update_indexes(canonical)
    _write(canonical / "GUI_DOMAIN_ADMISSION_AUTHORITY.json", _admission_authority())
    _write(canonical / "GUI_PERMISSION_AUDIT_AUTHORITY.json", _permission_authority())
    _write(canonical / "GUI_STATE_REASON_AUTHORITY.json", _state_reason_authority())
    _write(canonical / "GUI_TASK_METRIC_ADMISSION_AUTHORITY.json", _metric_authority())
    _write(canonical / "GUI_VIEW_CONTRACT.json", _view_authority())
    _compatibility(canonical)
    provenance = _load(canonical / "SOURCE_PROVENANCE.json")
    provenance["g1_v33_successor"] = {
        "decision_id": DECISION_ID,
        "parent_lock_sha256": predecessor_hash,
        "demo_target_sha256": "7aa5ff433fcaa49c3a54ac592acb43c42ee98fd944d4fb66de6e75bac2401a9a",
        "version_decision_sha256": _sha256(VERSION_DECISION),
    }
    _write(canonical / "SOURCE_PROVENANCE.json", provenance)
    artifacts = [
        {"file": path.name, "sha256": _sha256(path), "bytes": path.stat().st_size}
        for path in sorted(canonical.glob("*.json"), key=lambda item: item.name)
    ]
    lock = {
        "baseline": {
            "overall": "TPAA V8.0",
            "engineering": "ED-2.1",
            "core": NEW_CORE,
            "db_schema": DB_SCHEMA,
            "product": "P1_METRIC_CATALOG-1.14.0",
            "date": APPROVAL_DATE,
            "rebaseline": "R3.4_G1_V33_MACHINE_AUTHORITY",
            "decision_id": DECISION_ID,
            "lock_lineage_sha256": [predecessor_hash],
            "release_claim": False,
        },
        "artifacts": artifacts,
    }
    _write(destination / "BASELINE_LOCK.json", lock)
    _write(
        destination / "IMPORT_PROVENANCE.json",
        {
            "record_type": "G1_SUCCESSOR_IMPORT_PROVENANCE",
            "authority": False,
            "decision_id": DECISION_ID,
            "source_baseline": OLD_CORE,
            "source_baseline_lock_sha256": predecessor_hash,
            "core_baseline": NEW_CORE,
            "db_schema_target": DB_SCHEMA,
            "controlled_artifact_count": len(artifacts),
            "release_claim": False,
        },
    )
    (destination / "README.md").write_text(
        "# CB-1.6.0 G1 v33 successor baseline\n\n"
        f"Decision: `{DECISION_ID}`.\n\n"
        "CB-1.5.0 is the immutable direct parent. This local successor does not authorize "
        "repository push, production deployment or release.\n",
        encoding="utf-8",
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.check:
            if not TARGET_ROOT.is_dir():
                raise G1SuccessorError(f"successor is missing: {TARGET_ROOT}")
            with tempfile.TemporaryDirectory(prefix="tpaa-g1-") as temporary:
                generated = Path(temporary) / NEW_CORE
                build_successor(generated)
                expected, actual = _directory_digest(generated), _directory_digest(TARGET_ROOT)
                if expected != actual:
                    raise G1SuccessorError(f"successor drift: expected={expected} actual={actual}")
                print(f"G1_SUCCESSOR_PASS core={NEW_CORE} digest={actual}")
        else:
            build_successor(TARGET_ROOT)
            print(f"G1_SUCCESSOR_BUILT core={NEW_CORE} lock_sha256={_sha256(TARGET_ROOT / 'BASELINE_LOCK.json')}")
    except (OSError, ValueError, json.JSONDecodeError, G1SuccessorError) as exc:
        print(f"G1_SUCCESSOR_FAIL {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
