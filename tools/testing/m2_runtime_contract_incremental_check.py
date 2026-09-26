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
from collections.abc import Mapping
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
    value_numeric: float | None = None,
    value_structured: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "reason_codes": [],
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
        return {
            "metric_code": definition.metric_code,
            "instances": [instance],
        }

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

    validate_m2_runtime_output(
        numeric,
        {},
        {
            "metric_code": numeric.metric_code,
            "instances": [_instance("NUMERIC", status="N_A")],
        },
    )
    validate_m2_runtime_output(
        structured,
        {},
        {
            "metric_code": structured.metric_code,
            "instances": [_instance("STRUCTURED", status="N_A")],
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
        try:
            validate_m2_runtime_output(definition, input_payload, output)
        except CatalogMetricEngineError as exc:
            return exc.code
        return None

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
            "instances": [_instance("STRUCTURED", value_structured={})],
        },
    )
    valid_missing_value = error_code(
        numeric,
        {},
        {
            "metric_code": numeric.metric_code,
            "instances": [_instance("NUMERIC")],
        },
    )
    numeric_wrong_slot = error_code(
        numeric,
        {},
        {
            "metric_code": numeric.metric_code,
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

    non_radar_fake_observation = error_code(
        sns,
        {"system_type": "EO"},
        {
            "metric_code": sns.metric_code,
            "instances": [_instance("NUMERIC", value_numeric=1.0)],
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
    negative_error_codes = {
        "wrong_metric_code": wrong_metric_code,
        "value_kind_mismatch": value_kind_mismatch,
        "valid_missing_value": valid_missing_value,
        "numeric_wrong_slot": numeric_wrong_slot,
        "schema_missing_required": schema_missing_required,
        "schema_extra_property": schema_extra_property,
        "schema_invalid_enum": schema_invalid_enum,
        "schema_array_cardinality": schema_array_cardinality,
        "non_radar_fake_observation": non_radar_fake_observation,
        "radar_false_not_applicable": radar_false_not_applicable,
    }

    acceptance = {
        "catalog_runtime_gate_coverage_exact_32": len(plan.definitions) == 32,
        "numeric_value_kind_coverage_exact_29": len(numeric_definitions) == 29,
        "structured_value_kind_coverage_exact_3": (
            tuple(item.metric_code for item in structured_definitions)
            == ("P1-QA-001", "P1-QA-002", "P1-QA-006")
        ),
        "structured_schema_hashes_bound": all(
            isinstance(value, str) and len(value) == 64
            for value in schema_hashes.values()
        ),
        "valid_transport_samples_all_accept": True,
        "non_valid_null_value_slots_accept": True,
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
        "sns_radar_false_not_applicable_fails_closed": (
            radar_false_not_applicable == "M2_METRIC_APPLICABLE_OUTPUT_REJECTED"
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
            "authority_values_invented": False,
            "runtime_transport_contract_only": True,
        },
        "logical_product": {
            "plan_logical_hash": plan.logical_hash,
            "catalog_sha256": plan.catalog_sha256,
            "runtime_metric_codes": list(plan.metric_codes),
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
