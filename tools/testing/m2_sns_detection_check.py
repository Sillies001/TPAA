#!/usr/bin/env python3
"""Exact M2-MET-004 SNS detection evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = str(REPO_ROOT / "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from tpaa_metric import (  # noqa: E402
    SNS_DETECTION_CODES,
    CatalogMetricEngine,
    M2MetricPluginRequest,
    MetricPluginRegistry,
    build_m2_metric_execution_plan,
    build_m2_sns_detection_inputs,
    register_m2_sns_detection_plugins,
)
from tpaa_metric.operators import M2_OPERATOR_IMPLEMENTATIONS  # noqa: E402
from tpaa_metric.qa_foundation import (  # noqa: E402
    build_m2_qa_inputs,
    register_m2_qa_plugins,
)
from tpaa_world import project_m2_stage_world_lineage  # noqa: E402

AUTHORITY = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
M1_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "m1"
M2_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "m2"
RELEASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa8"


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


def _hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _opportunity(
    opportunity_id: str,
    start: int,
    end: int,
    *,
    status: str = "VALID",
    system_id: str,
) -> dict[str, object]:
    return {
        "opportunity_id": opportunity_id,
        "reference_entity_id": "target-1",
        "evaluated_system_instance_id": system_id,
        "start_session_time_us": start,
        "end_session_time_us": end,
        "validity_status": status,
        "opportunity_profile_id": "SNS_OPPORTUNITY_V1",
        "opportunity_profile_version": "1.0.0",
        "opportunity_profile_hash": "a" * 64,
        "eligibility_reason": "FROZEN_PROFILE_ELIGIBLE",
        "eligibility_provenance": "wre:synthetic-contract:v1",
    }


def _confirmation(opportunity_id: str, timestamp: int) -> dict[str, object]:
    return {
        "confirmation_event_id": f"confirmation-{opportunity_id}",
        "opportunity_id": opportunity_id,
        "reference_entity_id": "target-1",
        "first_confirmed_detection_time_us": timestamp,
        "confirmation_profile_id": "SNS_CONFIRMATION_V1",
        "confirmation_profile_version": "1.0.0",
        "confirmation_profile_hash": "b" * 64,
        "confirmation_persistence_s": 0.5,
        "association_provenance": "association:synthetic:v1",
    }


def _contracts(system_id: str) -> dict[str, list[dict[str, object]]]:
    return {
        "opportunities": [
            _opportunity("opp-1", 0, 4_000_000, system_id=system_id),
            _opportunity(
                "opp-invalid",
                4_000_000,
                6_000_000,
                status="INVALID",
                system_id=system_id,
            ),
            _opportunity("opp-2", 6_000_000, 10_000_000, system_id=system_id),
        ],
        "confirmations": [
            _confirmation("opp-1", 3_200_000),
            _confirmation("opp-2", 7_000_000),
        ],
        "target_presence_intervals": [
            {
                "evaluated_system_instance_id": system_id,
                "reference_entity_id": "target-1",
                "start_session_time_us": 0,
                "end_session_time_us": 10_000_000,
                "presence_provenance": "reference:synthetic:v1",
            }
        ],
        "reference_range_samples": [
            {
                "reference_state_id": "range-1-left",
                "reference_entity_id": "target-1",
                "session_time_us": 3_180_000,
                "reference_range_m": 6_820.0,
            },
            {
                "reference_state_id": "range-1-right",
                "reference_entity_id": "target-1",
                "session_time_us": 3_220_000,
                "reference_range_m": 6_780.0,
            },
            {
                "reference_state_id": "range-2-left",
                "reference_entity_id": "target-1",
                "session_time_us": 6_980_000,
                "reference_range_m": 3_020.0,
            },
            {
                "reference_state_id": "range-2-right",
                "reference_entity_id": "target-1",
                "session_time_us": 7_020_000,
                "reference_range_m": 2_980.0,
            },
        ],
    }


def _direct(
    plan: object,
    registry: MetricPluginRegistry,
    code: str,
    payload: Mapping[str, object],
) -> dict[str, object]:
    definition = plan.definition(code)  # type: ignore[attr-defined]
    _plugin_id, plugin = registry.resolve(
        definition.algorithm_id,
        definition.algorithm_version,
    )
    operators = MappingProxyType(
        {
            operator_id: M2_OPERATOR_IMPLEMENTATIONS[operator_id]
            for operator_id in definition.operator_bindings
        }
    )
    return dict(
        plugin(
            M2MetricPluginRequest(
                definition=definition,
                input_payload=payload,
                upstream_result_hashes=(),
                operators=operators,
            )
        )
    )


def _instances(output: Mapping[str, object]) -> list[dict[str, object]]:
    value = output.get("instances")
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("M2_SNS_EVIDENCE_OUTPUT_INVALID")
    return value


def verify() -> dict[str, object]:
    stage_world = project_m2_stage_world_lineage(
        M1_FIXTURES / "BF_M1_NOMINAL_V1",
        M2_FIXTURES / "RT_M2_NOMINAL_V1",
        M2_FIXTURES / "TA_M2_NOMINAL_V1",
        M2_FIXTURES / "MSI_M2_RADAR_V1",
        M2_FIXTURES / "MA_M2_NOMINAL_V1",
        authority_root=AUTHORITY,
        release_id=RELEASE_ID,
    )
    radar_world = stage_world.radar_sensor_world
    contracts = _contracts(radar_world.mission_system_instance_id)
    plan = build_m2_metric_execution_plan(AUTHORITY)
    registry = MetricPluginRegistry()
    register_m2_qa_plugins(plan, registry)
    register_m2_sns_detection_plugins(plan, registry)
    inputs = build_m2_qa_inputs(stage_world.reference_time_world, radar_world)
    inputs.update(
        build_m2_sns_detection_inputs(
            radar_world,
            stage_world,
            opportunities=contracts["opportunities"],
            confirmations=contracts["confirmations"],
            target_presence_intervals=contracts["target_presence_intervals"],
            reference_range_samples=contracts["reference_range_samples"],
        )
    )
    engine = CatalogMetricEngine(plan, registry)
    first = engine.execute(inputs, metric_codes=SNS_DETECTION_CODES)
    replayed = engine.execute(inputs, metric_codes=SNS_DETECTION_CODES)
    outputs = {code: _direct(plan, registry, code, inputs[code]) for code in SNS_DETECTION_CODES}

    rate_payload = dict(inputs["P1-SNS-002"])
    rate_payload["opportunities"] = [
        *[
            _opportunity(
                f"rate-{index}",
                index * 10,
                index * 10 + 9,
                system_id=radar_world.mission_system_instance_id,
            )
            for index in range(10)
        ],
        _opportunity(
            "rate-invalid",
            200,
            210,
            status="INVALID",
            system_id=radar_world.mission_system_instance_id,
        ),
    ]
    rate_payload["confirmations"] = [
        _confirmation(f"rate-{index}", index * 10 + 3) for index in range(8)
    ]
    rate_golden = _direct(plan, registry, "P1-SNS-002", rate_payload)

    missing_payload = dict(inputs["P1-SNS-003"])
    missing_payload["confirmations"] = [_confirmation("opp-1", 3_200_000)]
    missing_detection = _direct(plan, registry, "P1-SNS-003", missing_payload)

    gap_payload = dict(inputs["P1-SNS-004"])
    gap_payload["interpolation_max_gap_us"] = 10_000
    gap_range = _direct(plan, registry, "P1-SNS-004", gap_payload)

    non_radar = {}
    for code in SNS_DETECTION_CODES:
        payload = dict(inputs[code])
        payload["system_type"] = "IRST"
        non_radar[code] = _direct(plan, registry, code, payload)

    sns001 = _instances(outputs["P1-SNS-001"])
    sns003 = _instances(outputs["P1-SNS-003"])
    sns004 = _instances(outputs["P1-SNS-004"])
    rate_instance = _instances(rate_golden)[0]
    rate_evidence = rate_instance.get("evidence")
    if not isinstance(rate_evidence, dict):
        raise ValueError("M2_SNS_RATE_EVIDENCE_INVALID")
    missing_instances = _instances(missing_detection)
    gap_instances = _instances(gap_range)
    definitions = [plan.definition(code) for code in SNS_DETECTION_CODES]
    acceptance = {
        "catalog_membership_exact_4": tuple(item.metric_code for item in definitions)
        == SNS_DETECTION_CODES,
        "catalog_semantics_exact": all(
            item.family == "SENSOR_DETECTION"
            and item.subject_type == "MISSION_SYSTEM_INSTANCE"
            and item.value_kind == "NUMERIC"
            and item.structured_output_schema_id is None
            and item.publication_route == "SYSTEM_PERFORMANCE_OBSERVATION"
            and item.observation_lane == "SYSTEM_PERFORMANCE_OBSERVATION"
            for item in definitions
        ),
        "radar_applicability_exact": all(
            item.applicability.applicability_mode == "SYSTEM_TYPE_EXACT"
            and item.applicability.allowed_system_types == ("RADAR",)
            for item in definitions
        ),
        "shared_engine_dependency_closure_exact": first.metric_codes
        == ("P1-QA-005", *SNS_DETECTION_CODES),
        "shared_engine_dispatch_version_qualified": (
            first.dispatch_key == "algorithm_id+algorithm_version"
        ),
        "version_qualified_plugin_identity_exact": (
            {
                (algorithm_id, algorithm_version)
                for algorithm_id, algorithm_version, _plugin_id
                in registry.plugin_identity_manifest
                if algorithm_id in {item.algorithm_id for item in definitions}
            }
            == {
                (item.algorithm_id, item.algorithm_version)
                for item in definitions
            }
        ),
        "world_and_stage_lineage_bound": all(
            inputs[code]["world_logical_hash"] == radar_world.logical_hash
            and inputs[code]["stage_world_logical_hash"] == stage_world.logical_hash
            for code in SNS_DETECTION_CODES
        ),
        "upstream_contracts_consumed_not_rebuilt": all(
            inputs[code]["upstream_contracts_supplied"] is True
            and inputs[code]["opportunity_rebuilt_by_metric"] is False
            and inputs[code]["confirmation_rebuilt_by_metric"] is False
            for code in SNS_DETECTION_CODES
        ),
        "sns001_planned_off_coverage_golden": sns001[0]["value_numeric"] == 0.8,
        "sns002_ten_eight_invalid_excluded_golden": (
            rate_instance["value_numeric"] == 0.8
            and rate_evidence["invalid_opportunity_count"] == 1
        ),
        "sns003_first_detection_3_2s_golden": sns003[0]["value_numeric"] == 3.2,
        "sns003_missing_detection_na": (
            missing_instances[1]["status"] == "N_A"
            and missing_instances[1]["reason_codes"] == ["NO_CONFIRMED_DETECTION"]
        ),
        "sns004_linear_range_golden": sns004[0]["value_numeric"] == 6_800.0,
        "sns004_gap_not_bridged": (
            gap_instances[0]["status"] == "N_A"
            and gap_instances[0]["reason_codes"] == ["REFERENCE_RANGE_MATCH_UNAVAILABLE"]
        ),
        "non_radar_emits_no_fake_observation": all(
            output["applicable"] is False and output["instances"] == []
            for output in non_radar.values()
        ),
        "replay_exact": first == replayed,
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    logical_product = {
        "delivery_membership": list(SNS_DETECTION_CODES),
        "dependency_closure": list(first.metric_codes),
        "plan_logical_hash": plan.logical_hash,
        "world_logical_hash": radar_world.logical_hash,
        "stage_world_logical_hash": stage_world.logical_hash,
        "definition_hashes": {item.metric_code: item.definition_hash for item in definitions},
        "dispatch_key": first.dispatch_key,
        "engine_records": [
            {
                "metric_code": item.metric_code,
                "algorithm_id": item.algorithm_id,
                "algorithm_version": item.algorithm_version,
                "plugin_id": item.plugin_id,
                "dependency_manifest_hash": item.dependency_manifest_hash,
                "logical_hash": item.logical_hash,
            }
            for item in first.records
        ],
        "outputs": outputs,
        "rate_golden": rate_golden,
        "missing_detection": missing_detection,
        "gap_range": gap_range,
        "non_radar": non_radar,
        "contract_input_hash": _hash(contracts),
        "engine_logical_hash": first.logical_hash,
    }
    return {
        "schema": "TPAA_M2_MET_004_SNS_DETECTION_EVIDENCE_V1",
        "task_id": "M2-MET-004",
        "tracking_issue": 97,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "source_revision": _git_revision(),
        "logical_product": logical_product,
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
            "schema": "TPAA_M2_MET_004_SNS_DETECTION_EVIDENCE_V1",
            "task_id": "M2-MET-004",
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
