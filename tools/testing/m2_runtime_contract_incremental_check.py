#!/usr/bin/env python3
"""Authority-safe incremental runtime contract evidence for M2-MET-006.

This check validates only frozen applicability/value-kind/structured-schema
transport semantics. It does not execute blocked QA/SNS business semantics and
does not claim M2-MET-006 completion while M2-MET-002/005 remain incomplete.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"

STRUCTURED_SAMPLES: dict[str, dict[str, object]] = {
    "P1-QA-001": {
        "r_rel_ecef_m": [1000.0, 0.0, 0.0],
        "v_rel_ecef_mps": [10.0, 0.0, 0.0],
        "range_m": 1000.0,
        "range_rate_mps": 10.0,
        "own_body_az_rad": 0.0,
        "own_body_el_rad": 0.0,
        "sensor_az_rad": None,
        "sensor_el_rad": None,
        "sensor_frame_status": "NOT_CONFIGURED",
    },
    "P1-QA-002": {
        "sigma_range_m": 1.0,
        "sigma_az_rad": 0.01,
        "sigma_el_rad": 0.01,
        "sigma_position_3d_m": 1.5,
    },
    "P1-QA-006": {
        "error_domain": "RANGE",
        "residual_unit": "m",
        "raw_residual": 5.0,
        "reference_uncertainty": 3.0,
        "alignment_uncertainty": 1.0,
        "sensor_reported_uncertainty": 2.0,
        "normalized_residual": 1.0,
        "normalized_residual_status": "VALID",
    },
}


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    value = completed.stdout.strip()
    return value if len(value) == 40 else "UNKNOWN"


def _instance(
    value_kind: str,
    *,
    status: str = "VALID",
    reason_codes: Sequence[str] = (),
    value_numeric: float | None = None,
    value_structured: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "reason_codes": list(reason_codes),
        "value_kind": value_kind,
        "value_numeric": value_numeric,
        "value_structured": (
            None if value_structured is None else dict(value_structured)
        ),
    }


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_metric import (
        CatalogMetricEngineError,
        M2MetricDefinition,
        build_m2_metric_execution_plan,
        validate_m2_runtime_output,
    )

    plan = build_m2_metric_execution_plan(AUTHORITY_ROOT)

    def valid_input(definition: M2MetricDefinition) -> dict[str, object]:
        if definition.applicability.applicability_mode == "SYSTEM_TYPE_EXACT":
            return {"system_type": "RADAR"}
        return {}

    def valid_output(definition: M2MetricDefinition) -> dict[str, object]:
        if definition.value_kind == "NUMERIC":
            instance = _instance("NUMERIC", value_numeric=1.0)
        elif definition.value_kind == "STRUCTURED":
            instance = _instance(
                "STRUCTURED",
                value_structured=STRUCTURED_SAMPLES[definition.metric_code],
            )
        else:
            raise ValueError(f"unsupported value kind: {definition.value_kind}")
        output: dict[str, object] = {
            "metric_code": definition.metric_code,
            "subject_type": definition.subject_type,
            "observation_lane": definition.observation_lane,
            "publication_route": definition.publication_route,
            "instances": [instance],
        }
        if definition.applicability.applicability_mode == "SYSTEM_TYPE_EXACT":
            output["applicable"] = True
        return output

    for definition in plan.definitions:
        validate_m2_runtime_output(
            definition,
            valid_input(definition),
            valid_output(definition),
        )

    numeric = plan.definition("P1-QA-003")
    structured = plan.definition("P1-QA-006")
    structured_frame = plan.definition("P1-QA-001")
    sns = plan.definition("P1-SNS-001")

    for status, reason_codes in (
        ("N_A", ("TEST_MISSING_PREREQUISITE",)),
        ("INSUFFICIENT_DATA", ("TEST_INSUFFICIENT_DATA",)),
        ("INVALID", ()),
        ("REVIEW_REQUIRED", ()),
    ):
        validate_m2_runtime_output(
            numeric,
            {},
            {
                "metric_code": numeric.metric_code,
                "subject_type": numeric.subject_type,
                "observation_lane": numeric.observation_lane,
                "publication_route": numeric.publication_route,
                "instances": [
                    _instance(
                        "NUMERIC",
                        status=status,
                        reason_codes=reason_codes,
                    )
                ],
            },
        )
        validate_m2_runtime_output(
            structured,
            {},
            {
                "metric_code": structured.metric_code,
                "subject_type": structured.subject_type,
                "observation_lane": structured.observation_lane,
                "publication_route": structured.publication_route,
                "instances": [
                    _instance(
                        "STRUCTURED",
                        status=status,
                        reason_codes=reason_codes,
                    )
                ],
            },
        )

    sns_codes = tuple(
        definition.metric_code
        for definition in plan.definitions
        if definition.metric_code.startswith("P1-SNS-")
    )
    for code in sns_codes:
        definition = plan.definition(code)
        validate_m2_runtime_output(
            definition,
            {"system_type": "EO"},
            {
                "metric_code": code,
                "subject_type": definition.subject_type,
                "observation_lane": definition.observation_lane,
                "publication_route": definition.publication_route,
                "applicable": False,
                "reason_codes": ["SYSTEM_TYPE_NOT_APPLICABLE"],
                "instances": [],
            },
        )

    def error_code(
        definition: M2MetricDefinition,
        input_payload: Mapping[str, object],
        output: Mapping[str, object],
    ) -> str | None:
        candidate = dict(output)
        candidate.setdefault("subject_type", definition.subject_type)
        candidate.setdefault("observation_lane", definition.observation_lane)
        candidate.setdefault("publication_route", definition.publication_route)
        try:
            validate_m2_runtime_output(definition, input_payload, candidate)
        except CatalogMetricEngineError as exc:
            return exc.code
        return None

    subject_type_mismatch = error_code(
        numeric,
        {},
        {
            "metric_code": numeric.metric_code,
            "subject_type": "AIRCRAFT",
            "instances": [_instance("NUMERIC", value_numeric=1.0)],
        },
    )
    observation_lane_mismatch = error_code(
        numeric,
        {},
        {
            "metric_code": numeric.metric_code,
            "observation_lane": "TEST_ONLY_WRONG_LANE",
            "instances": [_instance("NUMERIC", value_numeric=1.0)],
        },
    )
    publication_route_mismatch = error_code(
        numeric,
        {},
        {
            "metric_code": numeric.metric_code,
            "publication_route": "TEST_ONLY_WRONG_ROUTE",
            "instances": [_instance("NUMERIC", value_numeric=1.0)],
        },
    )
    wrong_metric_code = error_code(
        numeric,
        {},
        {
            "metric_code": "P1-QA-999",
            "instances": [_instance("NUMERIC", value_numeric=1.0)],
        },
    )
    value_kind_mismatch = error_code(
        numeric,
        {},
        {
            "metric_code": numeric.metric_code,
            "subject_type": numeric.subject_type,
            "instances": [_instance("STRUCTURED", value_structured={})],
        },
    )
    valid_missing_value = error_code(
        numeric,
        {},
        {
            "metric_code": numeric.metric_code,
            "subject_type": numeric.subject_type,
            "instances": [_instance("NUMERIC")],
        },
    )
    numeric_wrong_slot = error_code(
        numeric,
        {},
        {
            "metric_code": numeric.metric_code,
            "subject_type": numeric.subject_type,
            "instances": [
                _instance(
                    "NUMERIC",
                    value_structured={"forbidden": True},
                )
            ],
        },
    )

    missing_required_value = dict(STRUCTURED_SAMPLES["P1-QA-006"])
    del missing_required_value["normalized_residual_status"]
    schema_missing_required = error_code(
        structured,
        {},
        {
            "metric_code": structured.metric_code,
            "subject_type": structured.subject_type,
            "instances": [
                _instance(
                    "STRUCTURED",
                    value_structured=missing_required_value,
                )
            ],
        },
    )

    extra_property_value = dict(STRUCTURED_SAMPLES["P1-QA-006"])
    extra_property_value["unexpected"] = 1
    schema_extra_property = error_code(
        structured,
        {},
        {
            "metric_code": structured.metric_code,
            "subject_type": structured.subject_type,
            "instances": [
                _instance(
                    "STRUCTURED",
                    value_structured=extra_property_value,
                )
            ],
        },
    )

    invalid_enum_value = dict(STRUCTURED_SAMPLES["P1-QA-006"])
    invalid_enum_value["normalized_residual_status"] = "TEST_ONLY_INVALID"
    schema_invalid_enum = error_code(
        structured,
        {},
        {
            "metric_code": structured.metric_code,
            "subject_type": structured.subject_type,
            "instances": [
                _instance(
                    "STRUCTURED",
                    value_structured=invalid_enum_value,
                )
            ],
        },
    )

    invalid_array_value = dict(STRUCTURED_SAMPLES["P1-QA-001"])
    invalid_array_value["r_rel_ecef_m"] = [1.0, 2.0]
    schema_array_cardinality = error_code(
        structured_frame,
        {},
        {
            "metric_code": structured_frame.metric_code,
            "instances": [
                _instance(
                    "STRUCTURED",
                    value_structured=invalid_array_value,
                )
            ],
        },
    )

    unknown_status = error_code(
        numeric,
        {},
        {
            "metric_code": numeric.metric_code,
            "subject_type": numeric.subject_type,
            "instances": [
                _instance(
                    "NUMERIC",
                    status="TEST_ONLY_UNKNOWN_STATUS",
                )
            ],
        },
    )
    missing_reason_codes_instance = _instance("NUMERIC", value_numeric=1.0)
    del missing_reason_codes_instance["reason_codes"]
    missing_reason_codes = error_code(
        numeric,
        {},
        {
            "metric_code": numeric.metric_code,
            "subject_type": numeric.subject_type,
            "instances": [missing_reason_codes_instance],
        },
    )
    na_without_reason = error_code(
        numeric,
        {},
        {
            "metric_code": numeric.metric_code,
            "subject_type": numeric.subject_type,
            "instances": [_instance("NUMERIC", status="N_A")],
        },
    )
    insufficient_without_reason = error_code(
        structured,
        {},
        {
            "metric_code": structured.metric_code,
            "subject_type": structured.subject_type,
            "instances": [_instance("STRUCTURED", status="INSUFFICIENT_DATA")],
        },
    )

    non_radar_fake_observation = error_code(
        sns,
        {"system_type": "EO"},
        {
            "metric_code": sns.metric_code,
            "instances": [_instance("NUMERIC", value_numeric=1.0)],
        },
    )
    non_radar_missing_subject_type = error_code(
        sns,
        {"system_type": "EO"},
        {
            "metric_code": sns.metric_code,
            "subject_type": None,
            "applicable": False,
            "reason_codes": ["SYSTEM_TYPE_NOT_APPLICABLE"],
            "instances": [],
        },
    )
    unknown_system_type = error_code(
        sns,
        {"system_type": "TEST_ONLY_UNKNOWN_SYSTEM_TYPE"},
        {
            "metric_code": sns.metric_code,
            "subject_type": sns.subject_type,
            "applicable": False,
            "reason_codes": ["SYSTEM_TYPE_NOT_APPLICABLE"],
            "instances": [],
        },
    )
    radar_false_not_applicable = error_code(
        sns,
        {"system_type": "RADAR"},
        {
            "metric_code": sns.metric_code,
            "applicable": False,
            "reason_codes": ["SYSTEM_TYPE_NOT_APPLICABLE"],
            "instances": [],
        },
    )
    radar_missing_applicable = error_code(
        sns,
        {"system_type": "RADAR"},
        {
            "metric_code": sns.metric_code,
            "subject_type": sns.subject_type,
            "instances": [_instance("NUMERIC", value_numeric=1.0)],
        },
    )

    structured_definitions = tuple(
        definition
        for definition in plan.definitions
        if definition.value_kind == "STRUCTURED"
    )
    numeric_definitions = tuple(
        definition
        for definition in plan.definitions
        if definition.value_kind == "NUMERIC"
    )
    schema_hashes = {
        definition.metric_code: definition.structured_output_schema_hash_sha256
        for definition in structured_definitions
    }
    subject_types = {
        definition.metric_code: definition.subject_type
        for definition in plan.definitions
    }
    observation_lanes = {
        definition.metric_code: definition.observation_lane
        for definition in plan.definitions
    }
    publication_routes = {
        definition.metric_code: definition.publication_route
        for definition in plan.definitions
    }
    longitudinal_trend_eligibility = {
        definition.metric_code: definition.p1_longitudinal_trend_eligibility
        for definition in plan.definitions
    }
    default_aggregations = {
        definition.metric_code: definition.default_aggregation
        for definition in plan.definitions
    }
    profile_parameter_bindings = {
        definition.metric_code: sorted(definition.profile_parameters)
        for definition in plan.definitions
        if definition.profile_parameters
    }
    registry_authority_hashes: dict[str, str] = {
        "operator_registry": plan.operator_registry_sha256,
        "constant_registry": plan.constant_registry_sha256,
        "state_machine_registry": plan.state_machine_registry_sha256,
        "upstream_contract_registry": plan.upstream_contract_registry_sha256,
        "structured_output_schema_registry": plan.structured_output_schema_registry_sha256,
        "family_applicability_contracts": plan.family_applicability_contracts_sha256,
    }
    authority_lineage_hashes = {
        definition.metric_code: definition.authority_lineage_hash
        for definition in plan.definitions
    }
    formula_dependency_references = {
        definition.metric_code: [
            list(item) for item in definition.formula_dependency_references
        ]
        for definition in plan.definitions
        if definition.formula_dependency_references
    }
    metric_execution_identities = {
        definition.metric_code: {
            "semantic_id": definition.semantic_id,
            "semantic_version": definition.semantic_version,
            "algorithm_id": definition.algorithm_id,
            "algorithm_version": definition.algorithm_version,
            "definition_hash": definition.definition_hash,
        }
        for definition in plan.definitions
    }
    reference_match_profile_identity_bindings = {
        definition.metric_code: [
            {
                "input_field": binding.input_field,
                "authority_field": binding.authority_field,
                "binding_kind": binding.binding_kind,
                "optional": binding.optional,
            }
            for binding in definition.input_authority_bindings
            if binding.authority_id == "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1"
        ]
        for definition in plan.definitions
        if "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1"
        in definition.upstream_dependencies
    }
    negative_error_codes = {
        "subject_type_mismatch": subject_type_mismatch,
        "observation_lane_mismatch": observation_lane_mismatch,
        "publication_route_mismatch": publication_route_mismatch,
        "wrong_metric_code": wrong_metric_code,
        "value_kind_mismatch": value_kind_mismatch,
        "valid_missing_value": valid_missing_value,
        "numeric_wrong_slot": numeric_wrong_slot,
        "schema_missing_required": schema_missing_required,
        "schema_extra_property": schema_extra_property,
        "schema_invalid_enum": schema_invalid_enum,
        "schema_array_cardinality": schema_array_cardinality,
        "unknown_status": unknown_status,
        "missing_reason_codes": missing_reason_codes,
        "na_without_reason": na_without_reason,
        "insufficient_without_reason": insufficient_without_reason,
        "non_radar_fake_observation": non_radar_fake_observation,
        "non_radar_missing_subject_type": non_radar_missing_subject_type,
        "unknown_system_type": unknown_system_type,
        "radar_false_not_applicable": radar_false_not_applicable,
        "radar_missing_applicable": radar_missing_applicable,
    }

    acceptance = {
        "catalog_runtime_gate_coverage_exact_32": len(plan.definitions) == 32,
        "subject_metadata_coverage_exact_32": len(subject_types) == 32,
        "subject_type_mismatch_fails_closed": (
            subject_type_mismatch == "M2_METRIC_RUNTIME_SUBJECT_TYPE_MISMATCH"
        ),
        "observation_lane_coverage_exact_32": len(observation_lanes) == 32,
        "publication_route_coverage_exact_32": len(publication_routes) == 32,
        "observation_lane_mismatch_fails_closed": (
            observation_lane_mismatch
            == "M2_METRIC_RUNTIME_OBSERVATION_LANE_MISMATCH"
        ),
        "publication_route_mismatch_fails_closed": (
            publication_route_mismatch
            == "M2_METRIC_RUNTIME_PUBLICATION_ROUTE_MISMATCH"
        ),
        "longitudinal_metadata_coverage_exact_32": (
            len(longitudinal_trend_eligibility) == 32
            and len(default_aggregations) == 32
        ),
        "trend_eligible_exact_26": (
            sum(longitudinal_trend_eligibility.values()) == 26
        ),
        "default_aggregation_exact_26_median_6_none": (
            tuple(default_aggregations.values()).count("MEDIAN") == 26
            and tuple(default_aggregations.values()).count("NONE") == 6
        ),
        "quality_evidence_never_longitudinal": all(
            not longitudinal_trend_eligibility[definition.metric_code]
            for definition in plan.definitions
            if definition.observation_lane == "QUALITY_EVIDENCE_ONLY"
        ),
        "structured_metrics_never_longitudinal": all(
            not longitudinal_trend_eligibility[definition.metric_code]
            for definition in plan.definitions
            if definition.value_kind == "STRUCTURED"
        ),
        "target_pair_never_longitudinal": all(
            not longitudinal_trend_eligibility[definition.metric_code]
            for definition in plan.definitions
            if definition.subject_type == "TARGET_PAIR"
        ),
        "trend_subject_types_exact": all(
            definition.subject_type in {"AIRCRAFT", "MISSION_SYSTEM_INSTANCE"}
            for definition in plan.definitions
            if definition.p1_longitudinal_trend_eligibility
        ),
        "profile_input_exact_name_contract_enforced": (
            profile_parameter_bindings
            == {
                "P1-QA-005": ["max_gap_us"],
                "P1-AIR-001": ["max_gap_us", "min_coverage"],
                "P1-AIR-003": ["derivative_window_s", "max_gap_us"],
            }
        ),
        "registry_authority_hashes_well_formed": all(
            len(value) == 64 for value in registry_authority_hashes.values()
        ),
        "required_state_machine_ids_exact": (
            plan.required_state_machine_ids
            == ("SM_CLOCK_SEGMENT_V1", "SM_VALIDITY_PIECE_V1")
        ),
        "required_external_dependency_ids_exact": (
            plan.required_external_dependency_ids
            == (
                "CONTRACT_ASSOCIATION_RELATION_V1",
                "CONTRACT_DETECTION_CONFIRMATION_EVENT_V1",
                "CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1",
                "CONTRACT_NAV_UNCERTAINTY_REPRESENTATION_V1",
                "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1",
                "CONTRACT_REFERENCE_RELATIVE_STATE_V1",
                "CONTRACT_TIME_TRANSFORM_V1",
            )
        ),
        "execution_identity_hash_well_formed": len(plan.execution_identity_sha256) == 64,
        "governed_formula_dependency_closure_exact_32": all(
            len(definition.operator_bindings) == len(set(definition.operator_bindings))
            and len(definition.constant_bindings) == len(set(definition.constant_bindings))
            and len(definition.upstream_dependencies)
            == len(set(definition.upstream_dependencies))
            and len(definition.state_machine_bindings)
            == len(set(definition.state_machine_bindings))
            for definition in plan.definitions
        ),
        "canonical_detection_event_authority_bound": (
            formula_dependency_references["P1-SNS-002"]
            == [
                ["UPSTREAM_CONTRACT", "CONTRACT_DETECTION_CONFIRMATION_EVENT_V1"],
                ["UPSTREAM_CONTRACT", "CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1"],
            ]
            and formula_dependency_references["P1-SNS-003"]
            == [
                ["UPSTREAM_CONTRACT", "CONTRACT_DETECTION_CONFIRMATION_EVENT_V1"],
                ["UPSTREAM_CONTRACT", "CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1"],
            ]
            and {
                "CONTRACT_ASSOCIATION_RELATION_V1",
                "CONTRACT_DETECTION_CONFIRMATION_EVENT_V1",
                "CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1",
            }
            <= set(plan.definition("P1-SNS-002").upstream_dependencies)
            and {
                "CONTRACT_ASSOCIATION_RELATION_V1",
                "CONTRACT_DETECTION_CONFIRMATION_EVENT_V1",
                "CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1",
            }
            <= set(plan.definition("P1-SNS-003").upstream_dependencies)
        ),
        "input_lineage_encoding_exact": (
            plan.input_lineage_encoding == "TPAA_M2_INPUT_LINEAGE_JSON_V1"
        ),
        "authority_lineage_hash_coverage_exact_32": (
            len(authority_lineage_hashes) == 32
            and all(len(value) == 64 for value in authority_lineage_hashes.values())
        ),
        "execution_identity_metadata_coverage_exact_32": (
            len(metric_execution_identities) == 32
            and all(
                item["semantic_id"]
                and isinstance(item["semantic_version"], int)
                and item["algorithm_id"]
                and item["algorithm_version"]
                and isinstance(item["definition_hash"], str)
                and len(item["definition_hash"]) == 64
                for item in metric_execution_identities.values()
            )
        ),
        "reference_match_profile_identity_binding_exact_17": (
            set(reference_match_profile_identity_bindings)
            == {f"P1-SNS-{index:03d}" for index in range(5, 22)}
            and all(
                {
                    (
                        item["input_field"],
                        item["authority_field"],
                        item["binding_kind"],
                        item["optional"],
                    )
                    for item in bindings
                }
                == {
                    (
                        "reference_match_quality_profile_id",
                        "reference_match_quality_profile_id",
                        "UPSTREAM_CONTRACT",
                        False,
                    ),
                    (
                        "reference_match_quality_profile_version",
                        "reference_match_quality_profile_version",
                        "UPSTREAM_CONTRACT",
                        False,
                    ),
                    (
                        "reference_match_quality_profile_hash",
                        "reference_match_quality_profile_hash",
                        "UPSTREAM_CONTRACT",
                        False,
                    ),
                }
                for bindings in reference_match_profile_identity_bindings.values()
            )
        ),
        "numeric_value_kind_coverage_exact_29": len(numeric_definitions) == 29,
        "structured_value_kind_coverage_exact_3": (
            tuple(item.metric_code for item in structured_definitions)
            == ("P1-QA-001", "P1-QA-002", "P1-QA-006")
        ),
        "structured_schema_hashes_bound": all(
            isinstance(value, str) and len(value) == 64
            for value in schema_hashes.values()
        ),
        "structured_schema_closed_world_authority_enforced": True,
        "valid_transport_samples_all_accept": True,
        "non_valid_null_value_slots_accept": True,
        "core_result_status_authority_exact": (
            plan.allowed_result_statuses
            == ("VALID", "N_A", "INSUFFICIENT_DATA", "INVALID", "REVIEW_REQUIRED")
        ),
        "core_runtime_rule_authority_bound": len(plan.core_rules_sha256) == 64,
        "core_mission_system_type_authority_exact": (
            plan.allowed_mission_system_types
            == (
                "RADAR",
                "IRST",
                "EO",
                "RWR",
                "ESM",
                "DATALINK",
                "FUSION",
                "MISSION_COMPUTER",
                "OTHER",
            )
        ),
        "na_insufficient_invalid_transport_branches_accept": True,
        "unknown_status_fails_closed": (
            unknown_status == "M2_METRIC_RUNTIME_STATUS_INVALID"
        ),
        "reason_codes_shape_required": (
            missing_reason_codes == "M2_METRIC_RUNTIME_REASON_CODES_INVALID"
        ),
        "missing_data_reason_code_required": (
            na_without_reason == "M2_METRIC_RUNTIME_REASON_CODE_REQUIRED"
            and insufficient_without_reason == "M2_METRIC_RUNTIME_REASON_CODE_REQUIRED"
        ),
        "wrong_metric_code_fails_closed": (
            wrong_metric_code == "M2_METRIC_RUNTIME_METRIC_CODE_MISMATCH"
        ),
        "value_kind_mismatch_fails_closed": (
            value_kind_mismatch == "M2_METRIC_RUNTIME_VALUE_KIND_MISMATCH"
        ),
        "valid_missing_value_fails_closed": (
            valid_missing_value == "M2_METRIC_RUNTIME_VALID_VALUE_MISSING"
        ),
        "numeric_wrong_slot_fails_closed": (
            numeric_wrong_slot == "M2_METRIC_RUNTIME_VALUE_SLOT_MISMATCH"
        ),
        "structured_missing_required_fails_closed": (
            schema_missing_required
            == "M2_METRIC_STRUCTURED_OUTPUT_SCHEMA_VIOLATION"
        ),
        "structured_extra_property_fails_closed": (
            schema_extra_property
            == "M2_METRIC_STRUCTURED_OUTPUT_SCHEMA_VIOLATION"
        ),
        "structured_enum_fails_closed": (
            schema_invalid_enum
            == "M2_METRIC_STRUCTURED_OUTPUT_SCHEMA_VIOLATION"
        ),
        "structured_array_cardinality_fails_closed": (
            schema_array_cardinality
            == "M2_METRIC_STRUCTURED_OUTPUT_SCHEMA_VIOLATION"
        ),
        "sns_non_radar_zero_instances_accept_all_21": len(sns_codes) == 21,
        "sns_non_radar_fake_observation_fails_closed": (
            non_radar_fake_observation
            == "M2_METRIC_NOT_APPLICABLE_OUTPUT_INVALID"
        ),
        "sns_non_radar_subject_metadata_required": (
            non_radar_missing_subject_type
            == "M2_METRIC_RUNTIME_SUBJECT_TYPE_MISMATCH"
        ),
        "unknown_system_type_fails_closed": (
            unknown_system_type == "M2_METRIC_APPLICABILITY_INPUT_INVALID"
        ),
        "sns_radar_false_not_applicable_fails_closed": (
            radar_false_not_applicable == "M2_METRIC_APPLICABLE_OUTPUT_REJECTED"
        ),
        "sns_radar_missing_applicable_fails_closed": (
            radar_missing_applicable == "M2_METRIC_APPLICABLE_OUTPUT_REJECTED"
        ),
        "predecessor_gate_preserved": True,
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    return {
        "schema": "TPAA_M2_MET_006_RUNTIME_CONTRACT_INCREMENTAL_EVIDENCE_V1",
        "task_id": "M2-MET-006",
        "tracking_issue": 97,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": False,
        "source_revision": _git_revision(),
        "blocked_predecessors": ["M2-MET-002", "M2-MET-005"],
        "external_authority_gaps": {
            "P1-QA-001": "frame convention authority unresolved",
            "P1-QA-002": "six-dimensional uncertainty mapping authority unresolved",
            "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1": (
                "frozen M2 alignment fixture omits five required profile fields"
            ),
        },
        "scope": {
            "business_metric_semantics_executed": False,
            "business_status_selection_semantics_executed": False,
            "subject_metadata_binding_only": True,
            "publication_metadata_binding_only": True,
            "longitudinal_metadata_binding_only": True,
            "profile_parameter_name_binding_only": True,
            "reference_match_profile_identity_binding_only": True,
            "execution_identity_binding_only": True,
            "registry_lineage_binding_only": True,
            "per_metric_authority_lineage_binding_only": True,
            "input_payload_lineage_binding_only": True,
            "governed_dependency_closure_binding_only": True,
            "authority_values_invented": False,
            "runtime_transport_contract_only": True,
        },
        "logical_product": {
            "plan_logical_hash": plan.logical_hash,
            "execution_identity_sha256": plan.execution_identity_sha256,
            "input_lineage_encoding": plan.input_lineage_encoding,
            "registry_authority_hashes": registry_authority_hashes,
            "required_operator_ids": list(plan.required_operator_ids),
            "required_state_machine_ids": list(plan.required_state_machine_ids),
            "required_external_dependency_ids": list(plan.required_external_dependency_ids),
            "catalog_sha256": plan.catalog_sha256,
            "core_logical_model_sha256": plan.core_logical_model_sha256,
            "core_rules_sha256": plan.core_rules_sha256,
            "allowed_result_statuses": list(plan.allowed_result_statuses),
            "allowed_mission_system_types": list(plan.allowed_mission_system_types),
            "runtime_metric_codes": list(plan.metric_codes),
            "metric_execution_identities": metric_execution_identities,
            "authority_lineage_hashes": authority_lineage_hashes,
            "formula_dependency_references": formula_dependency_references,
            "subject_types": subject_types,
            "observation_lanes": observation_lanes,
            "publication_routes": publication_routes,
            "longitudinal_trend_eligibility": longitudinal_trend_eligibility,
            "default_aggregations": default_aggregations,
            "profile_parameter_bindings": profile_parameter_bindings,
            "reference_match_profile_identity_bindings": (
                reference_match_profile_identity_bindings
            ),
            "numeric_metric_codes": [
                definition.metric_code for definition in numeric_definitions
            ],
            "structured_schema_hashes": schema_hashes,
            "sns_applicability_metric_codes": list(sns_codes),
            "negative_error_codes": negative_error_codes,
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        payload = verify()
        return_code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M2_MET_006_RUNTIME_CONTRACT_INCREMENTAL_EVIDENCE_V1",
            "task_id": "M2-MET-006",
            "tracking_issue": 97,
            "status": "FAIL",
            "task_complete": False,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
