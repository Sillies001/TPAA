#!/usr/bin/env python3
"""Verify the pre-admission M1-A/B/C detailed-design baseline.

This verifier proves that the implementation design still references the frozen
Canonical authorities correctly. It does not admit M1 and does not execute M1
feature code.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN = REPO_ROOT / "docs" / "design" / "M1" / "M1_A_C_DETAILED_DESIGN.json"
M1_C_DESIGN = (
    REPO_ROOT
    / "docs"
    / "design"
    / "M1"
    / "M1_C_EPISODE_STAGE_WORLD_IMPLEMENTATION_DESIGN.json"
)
FIXTURE_POLICY = REPO_ROOT / "tools" / "testing" / "M1_FIXTURE_POLICY.json"
CANONICAL_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
CORE_RULES = CANONICAL_ROOT / "CORE_RULES.json"
CORE_MODEL = CANONICAL_ROOT / "CORE_LOGICAL_MODEL.json"
STAGES = CANONICAL_ROOT / "STAGE_REGISTRY.json"
METRIC_INPUTS = CANONICAL_ROOT / "METRIC_INPUT_AUTHORITY_MATRIX.json"
WORLD_CAPABILITIES = CANONICAL_ROOT / "WORLD_CAPABILITY_REGISTRY.json"

EXPECTED_FIXTURES = {
    "BF_M1_NOMINAL_V1",
    "BF_M1_GAP_V1",
    "BF_M1_ANGLE_WRAP_V1",
    "BF_M1_STRUCTURED_PARTIAL_V1",
    "BF_M1_STAGE_BOUNDARY_V1",
    "BF_M1_REPLAY_V1",
    "BF_M1_CROSS_PLATFORM_V1",
    "BF_M1_FAILURE_V1",
}

EXPECTED_MANIFEST_FIELDS = {
    "fixture_id",
    "fixture_version",
    "input_sha256",
    "expected_sha256",
    "authority_refs",
    "tolerance_profile",
    "data_classification",
    "review_state",
}

EXPECTED_CHANNELS = {
    "body_p_rad_s",
    "nz_g",
    "heading_true_rad",
    "tas_mps",
    "mach",
    "session_time_us",
    "quality_mask",
}

EXPECTED_STAGE_ORDER = (
    "SETUP_ENTRY",
    "EXECUTION",
    "STABILIZATION_RECOVERY",
    "COMPLETION",
)

EXPECTED_PRECEDENCE = (
    "CONTEXT_OFFICIAL_MARKER",
    "NORMALIZED_AUTHORITY_EVENT",
    "CONTEXT_RULE_WORLD_DERIVATION",
    "MODEL_INFERENCE",
    "MANUAL_REVIEW",
)

EXPECTED_TABLES: dict[str, set[str]] = {
    "registry.training_session": {"session_id", "start_session_time_us", "end_session_time_us"},
    "registry.data_source": {
        "source_id",
        "session_id",
        "source_type",
        "time_basis",
        "source_quality",
        "ingest_adapter_id",
        "ingest_adapter_version",
    },
    "registry.source_stream": {"source_stream_id", "source_id", "ordinal_basis", "status"},
    "registry.source_artifact": {
        "artifact_id",
        "source_id",
        "source_stream_id",
        "sha256",
        "immutable",
    },
    "registry.dataset_manifest": {
        "dataset_id",
        "artifact_sha256",
        "logical_content_hash",
        "input_hash",
        "status",
    },
    "registry.context_artifact": {
        "context_artifact_id",
        "artifact_kind",
        "object_ref_id",
        "artifact_sha256",
    },
    "context.evaluation_context": {
        "context_id",
        "session_id",
        "rule_set_version",
        "metric_profile_version",
        "status",
    },
    "context.context_artifact_binding": {
        "context_id",
        "binding_role",
        "context_artifact_id",
    },
    "episode.training_episode": {
        "episode_id",
        "session_id",
        "episode_type",
        "context_id",
        "start_session_time_us",
        "end_session_time_us",
        "supersedes_episode_id",
    },
    "episode.episode_stage": {
        "stage_id",
        "episode_id",
        "stage_type",
        "stage_order",
        "start_session_time_us",
        "end_session_time_us",
        "stage_status",
        "coverage",
        "confidence",
        "detector_version",
        "supersedes_stage_id",
    },
}

REQUIRED_RULE_IDS = {"CR-003", "CR-004", "CR-005", "CR-006", "CR-018", "CR-027", "CR-028"}
REPRESENTATIVE_METRICS = {"P1-AIR-001", "P1-AIR-002", "P1-AIR-003", "P1-AIR-004", "P1-AIR-007"}
FORBIDDEN_M1_SENSOR_FAMILIES = {"RADAR", "IRST", "ESM", "DL", "FUS"}


def _load(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError(f"JSON root must be object: {path}")
    return raw


def _check(code: str, ok: bool, detail: str) -> dict[str, str]:
    return {"check": code, "status": "PASS" if ok else "FAIL", "detail": detail}


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def verify() -> dict[str, object]:
    design = _load(DESIGN)
    m1_c_design = _load(M1_C_DESIGN)
    fixture_policy = _load(FIXTURE_POLICY)
    core_rules = _load(CORE_RULES)
    core_model = _load(CORE_MODEL)
    stages = _load(STAGES)
    metric_inputs = _load(METRIC_INPUTS)
    world_capabilities = _load(WORLD_CAPABILITIES)

    checks: list[dict[str, str]] = []
    checks.append(
        _check(
            "design_schema",
            design.get("schema") == "TPAA_M1_A_C_DETAILED_DESIGN_BASELINE_V1",
            str(design.get("schema")),
        )
    )
    checks.append(
        _check(
            "design_role",
            design.get("document_role") == "IMPLEMENTATION_DESIGN_NOT_SEMANTIC_AUTHORITY",
            str(design.get("document_role")),
        )
    )

    guardrails = _mapping(design.get("guardrails"))
    exclusions = _string_set(guardrails.get("m1_vertical_slice_sensor_families_excluded"))
    checks.append(
        _check(
            "pre_admission_boundary",
            guardrails.get("pre_admission_feature_code_authorized") is False,
            str(guardrails.get("pre_admission_feature_code_authorized")),
        )
    )
    checks.append(
        _check(
            "m1_sensor_exclusions",
            exclusions == FORBIDDEN_M1_SENSOR_FAMILIES,
            ",".join(sorted(exclusions)),
        )
    )
    checks.append(
        _check(
            "platform_neutral_guardrail",
            guardrails.get("os_specific_business_semantics") is False,
            str(guardrails.get("os_specific_business_semantics")),
        )
    )

    wave_a = _mapping(design.get("wave_a_fixture_contract"))
    design_fixtures = _string_set(wave_a.get("bundle_ids"))
    policy_bundles = fixture_policy.get("bundles")
    policy_fixture_ids: set[str] = set()
    if isinstance(policy_bundles, list):
        for item in policy_bundles:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                policy_fixture_ids.add(item["id"])
    checks.append(
        _check(
            "fixture_ids",
            design_fixtures == EXPECTED_FIXTURES == policy_fixture_ids,
            f"design={len(design_fixtures)} policy={len(policy_fixture_ids)}",
        )
    )
    checks.append(
        _check(
            "fixture_manifest_fields",
            _string_set(wave_a.get("manifest_required_fields")) == EXPECTED_MANIFEST_FIELDS,
            ",".join(sorted(_string_set(wave_a.get("manifest_required_fields")))),
        )
    )
    lifecycle = wave_a.get("lifecycle")
    checks.append(
        _check(
            "fixture_lifecycle",
            lifecycle == ["DRAFT", "REVIEWED", "APPROVED_GOLDEN", "RETIRED"],
            str(lifecycle),
        )
    )

    wave_b = _mapping(design.get("wave_b_data_spine"))
    canonical = _mapping(wave_b.get("canonical_aircraft_state"))
    design_channels = _string_set(canonical.get("required_fields"))
    checks.append(
        _check(
            "canonical_channel_set",
            design_channels == EXPECTED_CHANNELS,
            ",".join(sorted(design_channels)),
        )
    )

    bindings = metric_inputs.get("bindings")
    authority_fields: set[str] = set()
    representative_seen: set[str] = set()
    if isinstance(bindings, list):
        for item in bindings:
            if not isinstance(item, dict):
                continue
            metric_code = item.get("metric_code")
            if metric_code not in REPRESENTATIVE_METRICS:
                continue
            representative_seen.add(str(metric_code))
            if (
                item.get("binding_kind") == "CANONICAL_FIELD"
                and item.get("authority_id") == "CANONICAL_AIRCRAFT_STATE_V1"
            ):
                authority_field = item.get("authority_field")
                if isinstance(authority_field, str):
                    authority_fields.add(authority_field)
    checks.append(
        _check(
            "representative_metric_bindings",
            representative_seen == REPRESENTATIVE_METRICS and EXPECTED_CHANNELS <= authority_fields,
            f"metrics={sorted(representative_seen)} fields={sorted(authority_fields)}",
        )
    )

    rules = core_rules.get("rules")
    rule_ids: set[str] = set()
    if isinstance(rules, list):
        for item in rules:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                rule_ids.add(item["id"])
    checks.append(
        _check(
            "core_rules",
            REQUIRED_RULE_IDS <= rule_ids,
            ",".join(sorted(REQUIRED_RULE_IDS & rule_ids)),
        )
    )

    tables = _mapping(core_model.get("tables"))
    missing_table_fields: list[str] = []
    for table_name, expected_fields in EXPECTED_TABLES.items():
        table = _mapping(tables.get(table_name))
        fields = table.get("fields")
        actual_fields: set[str] = set()
        if isinstance(fields, list):
            for field in fields:
                if isinstance(field, dict) and isinstance(field.get("name"), str):
                    actual_fields.add(field["name"])
        missing = expected_fields - actual_fields
        if missing:
            missing_table_fields.append(f"{table_name}:{','.join(sorted(missing))}")
    checks.append(
        _check(
            "logical_model_contracts",
            not missing_table_fields,
            (
                "; ".join(missing_table_fields)
                if missing_table_fields
                else "all required table fields present"
            ),
        )
    )

    stage_governance = _mapping(stages.get("governance"))
    profiles = _mapping(stages.get("profiles"))
    basic = _mapping(profiles.get("BASIC_FLIGHT_V1"))
    ordered = basic.get("ordered_stages")
    precedence = stage_governance.get("precedence")
    checks.append(
        _check(
            "basic_flight_stage_order",
            ordered == list(EXPECTED_STAGE_ORDER),
            str(ordered),
        )
    )
    checks.append(
        _check(
            "stage_precedence",
            precedence == list(EXPECTED_PRECEDENCE),
            str(precedence),
        )
    )
    checks.append(
        _check(
            "stage_interval",
            stage_governance.get("time_interval")
            == "half-open [start_session_time_us,end_session_time_us)",
            str(stage_governance.get("time_interval")),
        )
    )

    evaluation = _mapping(wave_b.get("evaluation_context"))
    stage_selection = _mapping(evaluation.get("stage_profile_selection"))
    checks.append(
        _check(
            "no_invented_stage_binding",
            stage_selection.get("profile_id") == "BASIC_FLIGHT_V1"
            and stage_selection.get("new_context_binding_role_invented") is False,
            str(stage_selection),
        )
    )

    packages = _mapping(wave_b.get("package_ownership"))
    packages_ok = all((REPO_ROOT / path).exists() for path in packages)
    checks.append(
        _check(
            "package_targets_exist",
            packages_ok,
            ",".join(sorted(packages)),
        )
    )

    m1_c_prerequisites = _string_set(m1_c_design.get("implementation_prerequisites"))
    checks.append(
        _check(
            "m1_c_design_schema",
            m1_c_design.get("schema")
            == "TPAA_M1_C_EPISODE_STAGE_WORLD_IMPLEMENTATION_DESIGN_V1",
            str(m1_c_design.get("schema")),
        )
    )
    checks.append(
        _check(
            "m1_c_design_role",
            m1_c_design.get("document_role")
            == "IMPLEMENTATION_DESIGN_NOT_SEMANTIC_AUTHORITY"
            and m1_c_design.get("implementation_state") == "DESIGN_ONLY",
            str(m1_c_design.get("implementation_state")),
        )
    )
    checks.append(
        _check(
            "m1_c_data_spine_prerequisites",
            m1_c_prerequisites
            == {
                "M1-DATA-001",
                "M1-DATA-002",
                "M1-DATA-003",
                "M1-DATA-004",
                "M1-DATA-005",
                "M1-DATA-006",
                "M1-DATA-007",
            },
            ",".join(sorted(m1_c_prerequisites)),
        )
    )

    episode_contract = _mapping(m1_c_design.get("episode_contract"))
    episode_table = _mapping(tables.get("episode.training_episode"))
    episode_fields = episode_table.get("fields")
    actual_episode_fields: set[str] = set()
    if isinstance(episode_fields, list):
        for field in episode_fields:
            if isinstance(field, dict) and isinstance(field.get("name"), str):
                actual_episode_fields.add(field["name"])
    required_episode_fields = {
        "episode_id",
        "session_id",
        "episode_type",
        "context_id",
        "start_session_time_us",
        "end_session_time_us",
        "subject_scope",
        "primary_aircraft_id",
        "episode_status",
        "detector_version",
        "coverage",
        "confidence",
        "data_sufficiency_status",
        "supersedes_episode_id",
    }
    checks.append(
        _check(
            "m1_c_episode_contract",
            episode_contract.get("table_authority") == "episode.training_episode"
            and episode_contract.get("episode_type") == "BASIC_FLIGHT"
            and episode_contract.get("subject_scope") == "AIRCRAFT"
            and episode_contract.get("interval")
            == "[start_session_time_us,end_session_time_us)"
            and required_episode_fields <= actual_episode_fields,
            str(episode_contract.get("detector_version")),
        )
    )

    m1_c_stage = _mapping(m1_c_design.get("stage_contract"))
    fixture_marker_contract = _mapping(m1_c_stage.get("fixture_marker_contract"))
    checks.append(
        _check(
            "m1_c_stage_contract",
            m1_c_stage.get("profile_id") == "BASIC_FLIGHT_V1"
            and m1_c_stage.get("ordered_stages") == list(EXPECTED_STAGE_ORDER)
            and m1_c_stage.get("precedence") == list(EXPECTED_PRECEDENCE)
            and m1_c_stage.get("detection_method_mapping")
            == stage_governance.get("detection_method_mapping")
            and fixture_marker_contract.get("published_stage_markers")
            == list(EXPECTED_STAGE_ORDER)
            and fixture_marker_contract.get("terminator_marker") == "END"
            and fixture_marker_contract.get("terminator_is_stage") is False,
            str(m1_c_stage.get("profile_id")),
        )
    )

    world_contract = _mapping(m1_c_design.get("world_contract"))
    capabilities = _mapping(world_capabilities.get("capabilities"))
    basic_core = _mapping(capabilities.get("BASIC_CORE"))
    world_table = _mapping(tables.get("world.world_product_manifest"))
    world_fields = world_table.get("fields")
    actual_world_fields: set[str] = set()
    world_kind_sql = ""
    if isinstance(world_fields, list):
        for field in world_fields:
            if not isinstance(field, dict):
                continue
            name = field.get("name")
            if isinstance(name, str):
                actual_world_fields.add(name)
            sql = field.get("sql")
            if name == "world_kind" and isinstance(sql, str):
                world_kind_sql = sql
    allowed_world_kinds = _string_set(world_contract.get("allowed_world_kind_authority"))
    required_world_fields = {
        "world_product_id",
        "release_id",
        "session_id",
        "episode_id",
        "stage_id",
        "world_kind",
        "aircraft_id",
        "dataset_id",
        "start_session_time_us",
        "end_session_time_us",
        "status",
        "coverage",
        "confidence",
        "world_version",
        "policy_version",
        "logical_content_hash",
        "request_hash",
        "supersedes_id",
    }
    checks.append(
        _check(
            "m1_c_world_contract",
            world_contract.get("manifest_authority") == "world.world_product_manifest"
            and world_contract.get("capability_code") == "BASIC_CORE"
            and world_contract.get("required_capability_letters") == basic_core.get("required")
            and world_contract.get("optional_capability_letters") == basic_core.get("optional")
            and required_world_fields <= actual_world_fields
            and allowed_world_kinds
            == {"CONTEXT", "TRUTH", "PERCEPTION", "ACTION", "ADJUDICATION", "MACHINE"}
            and all(kind in world_kind_sql for kind in allowed_world_kinds)
            and world_contract.get("truth_may_substitute_for_missing_perception") is False
            and world_contract.get("missing_adjudication_may_be_inferred") is False,
            str(world_contract.get("capability_code")),
        )
    )

    stage_golden = _mapping(m1_c_design.get("stage_golden"))
    checks.append(
        _check(
            "m1_c_stage_golden_gate",
            stage_golden.get("task_id") == "M1-TST-003"
            and stage_golden.get("required_before_metric_vertical_slice") is True
            and stage_golden.get("primary_fixture") == "BF_M1_NOMINAL_V1"
            and stage_golden.get("boundary_fixture") == "BF_M1_STAGE_BOUNDARY_V1"
            and stage_golden.get("expected_result_independence_required") is True
            and stage_golden.get("metric_code_must_not_resegment_stage") is True,
            str(stage_golden.get("task_id")),
        )
    )

    m1_c_guardrails = _mapping(m1_c_design.get("guardrails"))
    checks.append(
        _check(
            "m1_c_guardrails",
            m1_c_guardrails.get("canonical_semantics_may_be_redefined") is False
            and m1_c_guardrails.get("stage_semantics_may_be_redefined") is False
            and m1_c_guardrails.get("m2_sensor_family_implementation_allowed") is False
            and m1_c_guardrails.get("metric_business_logic_implemented_by_this_design") is False
            and m1_c_guardrails.get("database_migration_required_by_this_design") is False
            and m1_c_guardrails.get("os_specific_business_semantics") is False,
            str(m1_c_guardrails),
        )
    )

    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return {
        "schema": "TPAA_M1_DETAILED_DESIGN_VERIFICATION_V1",
        "status": status,
        "admission": "NOT_DECIDED_BY_DESIGN_VERIFIER",
        "checks": checks,
    }


def main() -> int:
    result = verify()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
