#!/usr/bin/env python3
"""M3-MET-005 exact P1 passive-sensor remainder qualification evidence."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from tpaa_metric.catalog_engine import M2MetricExecutionPlan, MetricPluginRegistry

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
MISSION_FIXTURE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "m3"
    / "M3_WORLD_004_MISSION_SYSTEMS_V1.json"
)
TRACKING_ISSUE = 114
IRST_ID = "62222222-2222-4222-8222-222222222222"
EO_ID = "63333333-3333-4333-8333-333333333333"
RADAR_ID = "68888888-8888-4888-8888-888888888888"
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


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


def _load(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{path}: root must be string-keyed object")
    return cast(dict[str, object], raw)


def _quality(system_type: str) -> dict[str, object]:
    return {
        "system_type": system_type,
        "reference_match_quality_profile_id": "Q-PROFILE",
        "reference_match_quality_profile_version": "1.0.0",
        "reference_match_quality_profile_hash": HASH_A,
    }


def _opportunity_identity() -> dict[str, object]:
    return {
        "opportunity_profile_id": "OPP",
        "opportunity_profile_version": "1.0.0",
        "opportunity_profile_hash": HASH_B,
    }


def _coverage_identity() -> dict[str, object]:
    return {
        "reference_target_coverage_id": "COVERAGE",
        "reference_target_coverage_version": "1.0.0",
        "reference_target_coverage_hash": HASH_C,
    }


def _golden_inputs(system_type: str) -> dict[str, dict[str, object]]:
    angle_a = 0.1
    angle_b = 0.2
    base_quality = _quality(system_type)
    opportunity = _opportunity_identity()
    tracks = [
        {
            "track_id": f"T{index}",
            "stable_start_time_us": 0,
            "stable_end_time_us": 2_000_000,
            "association_status": "NO_MATCH" if index >= 8 else "MATCHED",
        }
        for index in range(10)
    ]
    tracks.append(
        {
            "track_id": "TA",
            "stable_start_time_us": 0,
            "stable_end_time_us": 2_000_000,
            "association_status": "AMBIGUOUS",
        }
    )
    return {
        "P1-PSV-001": {
            **base_quality,
            "samples": [
                {
                    "reference_match_accepted": True,
                    "error_domain": "LOS_ANGLE",
                    "measured_los_unit": [math.cos(angle_a), math.sin(angle_a), 0.0],
                    "reference_los_unit": [1.0, 0.0, 0.0],
                },
                {
                    "reference_match_accepted": True,
                    "error_domain": "LOS_ANGLE",
                    "measured_los_unit": [math.cos(angle_b), math.sin(angle_b), 0.0],
                    "reference_los_unit": [1.0, 0.0, 0.0],
                },
            ],
        },
        "P1-PSV-002": {
            **base_quality,
            "samples": [
                {
                    "reference_match_accepted": True,
                    "error_domain": "LOS_RATE",
                    "measured_los_rate_rad_s": 2.0,
                    "reference_los_rate_rad_s": 1.0,
                },
                {
                    "reference_match_accepted": True,
                    "error_domain": "LOS_RATE",
                    "measured_los_rate_rad_s": 1.0,
                    "reference_los_rate_rad_s": 2.0,
                },
            ],
        },
        "P1-PSV-003": {
            **base_quality,
            "samples": [
                {
                    "reference_match_accepted": True,
                    "error_domain": "RANGE",
                    "passive_range_estimate_m": 1100.0,
                    "reference_range_m": 1000.0,
                },
                {
                    "reference_match_accepted": True,
                    "error_domain": "RANGE",
                    "passive_range_estimate_m": 900.0,
                    "reference_range_m": 1000.0,
                },
            ],
        },
        "P1-PSV-004": {
            "system_type": system_type,
            **opportunity,
            "confirmation_profile_id": "CONF",
            "confirmation_profile_version": "1.0.0",
            "confirmation_profile_hash": HASH_C,
            "evaluation_opportunity_intervals": [
                {
                    "detection_opportunity_id": f"O{index}",
                    "reference_target_id": f"R{index}",
                    "start_session_time_us": index * 2_000_000,
                    "end_session_time_us": (index + 1) * 2_000_000,
                }
                for index in range(3)
            ],
            "confirmation_events": [
                {
                    "detection_confirmation_event_id": f"C{index}",
                    "detection_opportunity_id": f"O{index}",
                    "reference_target_id": f"R{index}",
                }
                for index in range(2)
            ],
        },
        "P1-PSV-005": {
            "system_type": system_type,
            **opportunity,
            "evaluation_opportunity_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 10_000_000}
            ],
            "passive_track_valid_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 4_000_000},
                {"start_session_time_us": 6_000_000, "end_session_time_us": 10_000_000},
            ],
        },
        "P1-PSV-006": {
            "system_type": system_type,
            "profile": {
                "drop_min_duration_s": 1.0,
                "reacquisition_persistence_s": 1.0,
                "max_gap_us": 500_000,
            },
            "reacquisition_events": [
                {
                    "passive_drop_time_us": 0,
                    "passive_reacquired_time_us": delay * 1_000_000,
                    "invalid_dwell_s": 1.5,
                    "stable_persistence_s": 1.5,
                    "same_reference_association": True,
                }
                for delay in (2, 4, 6)
            ],
        },
        "P1-PSV-007": {
            "system_type": system_type,
            **_coverage_identity(),
            "reference_target_coverage_status": "COMPLETE",
            "evaluation_start_time_us": 0,
            "evaluation_end_time_us": 10_000_000,
            "coverage_start_time_us": 0,
            "coverage_end_time_us": 10_000_000,
            "profile": {
                "stable_track_persistence_s": 1.0,
                "max_gap_us": 500_000,
            },
            "passive_tracks": tracks,
        },
    }


def _instance(output: Mapping[str, object]) -> Mapping[str, object]:
    raw = output.get("instances")
    if not isinstance(raw, list) or len(raw) != 1 or not isinstance(raw[0], dict):
        raise ValueError("expected one metric instance")
    return cast(Mapping[str, object], raw[0])


def _direct_outputs(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
    inputs: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    from tpaa_metric.catalog_engine import (
        M2MetricPluginRequest,
        validate_m2_runtime_output,
    )
    from tpaa_metric.m3_air_operators import M3_AIR_OPERATOR_IMPLEMENTATIONS
    from tpaa_metric.m3_passive import M3_PSV_CODES

    outputs: dict[str, dict[str, object]] = {}
    for code in M3_PSV_CODES:
        definition = plan.definition(code)
        _plugin_id, plugin = registry.resolve(
            definition.algorithm_id,
            definition.algorithm_version,
        )
        request = M2MetricPluginRequest(
            definition=definition,
            input_payload=inputs[code],
            upstream_result_hashes=(
                ("P1-QA-001", "1" * 64),
                ("P1-QA-002", "2" * 64),
                ("P1-QA-005", "5" * 64),
            ),
            operators={
                operator_id: M3_AIR_OPERATOR_IMPLEMENTATIONS[operator_id]
                for operator_id in definition.operator_bindings
            },
        )
        output = dict(plugin(request))
        validate_m2_runtime_output(definition, inputs[code], output)
        outputs[code] = output
    return outputs


def _dependency_probe(request: object) -> dict[str, object]:
    return {"dependency_probe": type(request).__name__}


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_metric import CatalogMetricEngine, MetricPluginRegistry
    from tpaa_metric.m3_air_operators import M3_AIR_OPERATOR_IMPLEMENTATIONS
    from tpaa_metric.m3_general_engine import build_m3_metric_execution_plan
    from tpaa_metric.m3_passive import (
        M3_PSV_ALLOWED_SYSTEM_TYPES,
        M3_PSV_CODES,
        register_m3_passive_plugins,
    )
    from tpaa_world.m3_mission_product_applicability import (
        load_m3_mission_product_inputs,
        project_m3_family_applicability,
    )

    world = load_m3_mission_product_inputs(
        MISSION_FIXTURE,
        authority_root=AUTHORITY_ROOT,
    )
    subjects = {
        subject.mission_system_instance_id: subject
        for subject in world.subjects
    }
    irst = subjects[IRST_ID]
    eo = subjects[EO_ID]
    radar = subjects[RADAR_ID]
    irst_app = project_m3_family_applicability(
        world,
        family_code="P1-PSV-*",
        mission_system_instance_id=IRST_ID,
    )
    eo_app = project_m3_family_applicability(
        world,
        family_code="P1-PSV-*",
        mission_system_instance_id=EO_ID,
    )
    radar_app = project_m3_family_applicability(
        world,
        family_code="P1-PSV-*",
        mission_system_instance_id=RADAR_ID,
    )

    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    definitions = tuple(
        sorted(
            (
                definition
                for definition in plan.definitions
                if definition.metric_code in M3_PSV_CODES
            ),
            key=lambda definition: definition.metric_code,
        )
    )
    registry = MetricPluginRegistry()
    register_m3_passive_plugins(plan, registry)
    for code in ("P1-QA-001", "P1-QA-002", "P1-QA-005"):
        definition = plan.definition(code)
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m3-met-005-upstream-probe:{code}:v1",
            plugin=_dependency_probe,
        )

    positive_inputs = _golden_inputs("IRST")
    engine_inputs: dict[str, Mapping[str, object]] = {
        **positive_inputs,
        "P1-QA-001": {"probe": "qa001"},
        "P1-QA-002": {"probe": "qa002"},
        "P1-QA-005": {"probe": "qa005"},
    }
    engine = CatalogMetricEngine(
        plan,
        registry,
        operator_implementations=M3_AIR_OPERATOR_IMPLEMENTATIONS,
    )
    first = engine.execute(
        engine_inputs,
        metric_codes=M3_PSV_CODES,
        validate_runtime_contract=False,
    )
    replay = engine.execute(
        engine_inputs,
        metric_codes=M3_PSV_CODES,
        validate_runtime_contract=False,
    )
    direct = _direct_outputs(plan, registry, positive_inputs)
    direct_replay = _direct_outputs(plan, registry, positive_inputs)
    eo_direct = _direct_outputs(plan, registry, _golden_inputs("EO"))
    negative_inputs = {
        code: {"system_type": "RADAR"}
        for code in M3_PSV_CODES
    }
    negative_direct = _direct_outputs(plan, registry, negative_inputs)

    records = tuple(
        record for record in first.records if record.metric_code in M3_PSV_CODES
    )
    golden_numeric = {
        code: _instance(direct[code]).get("value_numeric")
        for code in M3_PSV_CODES
    }
    psv006_evidence = _instance(direct["P1-PSV-006"]).get("evidence")
    psv007_evidence = _instance(direct["P1-PSV-007"]).get("evidence")
    negative_exact = all(
        output.get("applicable") is False and output.get("instances") == []
        for output in negative_direct.values()
    )
    eo_exact = all(
        output.get("applicable") is True
        and _instance(output).get("status") == "VALID"
        for output in eo_direct.values()
    )

    quality_negative_inputs = _golden_inputs("IRST")
    quality_rows = quality_negative_inputs["P1-PSV-003"]["samples"]
    if not isinstance(quality_rows, list):
        raise ValueError("quality negative rows invalid")
    for row in quality_rows:
        if not isinstance(row, dict):
            raise ValueError("quality negative row invalid")
        row["reference_match_accepted"] = False
    quality_negative = _direct_outputs(
        plan,
        registry,
        quality_negative_inputs,
    )["P1-PSV-003"]

    coverage_negative_inputs = _golden_inputs("IRST")
    coverage_negative_inputs["P1-PSV-007"][
        "reference_target_coverage_status"
    ] = "PARTIAL"
    coverage_negative = _direct_outputs(
        plan,
        registry,
        coverage_negative_inputs,
    )["P1-PSV-007"]

    acceptance = {
        "passive_remainder_exact_7": (
            tuple(item.metric_code for item in definitions) == M3_PSV_CODES
        ),
        "passive_family_exact": {item.family for item in definitions} == {"PASSIVE_SENSOR"},
        "system_type_set_exact_irst_eo": all(
            item.applicability.applicability_mode == "SYSTEM_TYPE_SET"
            and item.applicability.allowed_system_types == M3_PSV_ALLOWED_SYSTEM_TYPES
            for item in definitions
        ),
        "world_irst_applicable": (
            irst.system_type == "IRST"
            and irst_app.applicable
            and irst_app.product_input_emitted
        ),
        "world_eo_applicable": (
            eo.system_type == "EO"
            and eo_app.applicable
            and eo_app.product_input_emitted
        ),
        "world_radar_fails_closed": (
            radar.system_type == "RADAR"
            and not radar_app.applicable
            and not radar_app.product_input_emitted
        ),
        "single_catalog_engine_dispatch": (
            len(records) == 7
            and {record.plugin_id for record in records}
            == {
                f"m3-passive-remainder:{code}:v1"
                for code in M3_PSV_CODES
            }
        ),
        "execution_replay_exact": first == replay,
        "plugin_replay_exact": direct == direct_replay,
        "eo_execution_exact_7": eo_exact,
        "radar_execution_fails_closed_exact_7": negative_exact,
        "runtime_contract_system_type_set_enforced": negative_exact,
        "quality_rejected_all_is_na": (
            _instance(quality_negative).get("status") == "N_A"
            and _instance(quality_negative).get("value_numeric") is None
        ),
        "partial_reference_coverage_is_na": (
            _instance(coverage_negative).get("status") == "N_A"
            and _instance(coverage_negative).get("value_numeric") is None
        ),
        "golden_los_angular_rmse": math.isclose(
            cast(float, golden_numeric["P1-PSV-001"]),
            math.sqrt((0.1**2 + 0.2**2) / 2.0),
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
        "golden_los_rate_rmse_1": golden_numeric["P1-PSV-002"] == 1.0,
        "golden_range_rmse_100": golden_numeric["P1-PSV-003"] == 100.0,
        "golden_detection_rate_2_over_3": golden_numeric["P1-PSV-004"] == 2.0 / 3.0,
        "golden_track_continuity_0_8": golden_numeric["P1-PSV-005"] == 0.8,
        "golden_reacquisition_median_4": golden_numeric["P1-PSV-006"] == 4.0,
        "golden_reacquisition_p95_evidence": (
            isinstance(psv006_evidence, dict)
            and psv006_evidence.get("p95_reacquisition_delay_s") == 5.8
        ),
        "golden_false_track_rate_0_2": golden_numeric["P1-PSV-007"] == 0.2,
        "ambiguous_false_track_excluded": (
            isinstance(psv007_evidence, dict)
            and psv007_evidence.get("excluded_ambiguous_track_count") == 1
        ),
    }
    failed = sorted(key for key, passed in acceptance.items() if not bool(passed))
    logical_product = {
        "metric_codes": list(M3_PSV_CODES),
        "allowed_system_types": list(M3_PSV_ALLOWED_SYSTEM_TYPES),
        "world_subjects": {
            "IRST": irst.mission_system_instance_id,
            "EO": eo.mission_system_instance_id,
            "negative_RADAR": radar.mission_system_instance_id,
        },
        "execution_metric_codes": list(first.metric_codes),
        "golden_numeric": golden_numeric,
        "record_hashes": [
            [record.metric_code, record.logical_hash]
            for record in records
        ],
        "execution_logical_hash": first.logical_hash,
    }
    return {
        "schema": "TPAA_M3_MET_005_PASSIVE_REMAINDER_EVIDENCE_V1",
        "task_id": "M3-MET-005",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": _git_revision(),
        "task_complete": not failed,
        "implementation_complete": not failed,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "exact_passive_remainder_7": True,
            "shared_catalog_engine": True,
            "system_type_set_irst_eo_only": True,
            "golden_and_negative_cases_executed": True,
            "persistence_executed": False,
            "publication_executed": False,
        },
    }


def compare_evidence(
    windows_path: Path,
    linux_path: Path,
    *,
    expected_revision: str,
) -> dict[str, object]:
    windows = _load(windows_path)
    linux = _load(linux_path)
    checks = {
        "windows_status_pass": windows.get("status") == "PASS",
        "linux_status_pass": linux.get("status") == "PASS",
        "windows_revision_exact": windows.get("source_revision") == expected_revision,
        "linux_revision_exact": linux.get("source_revision") == expected_revision,
        "windows_task_complete": windows.get("task_complete") is True,
        "linux_task_complete": linux.get("task_complete") is True,
        "logical_product_equal": windows.get("logical_product") == linux.get("logical_product"),
        "acceptance_equal": windows.get("acceptance") == linux.get("acceptance"),
        "failed_acceptance_empty": (
            windows.get("failed_acceptance") == []
            and linux.get("failed_acceptance") == []
        ),
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    return {
        "schema": "TPAA_M3_MET_005_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": "M3-MET-005",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": expected_revision,
        "windows_source_revision": windows.get("source_revision"),
        "linux_source_revision": linux.get("source_revision"),
        "logical_product": windows.get("logical_product"),
        "checks": checks,
        "failed_acceptance": failed,
    }


def _write(payload: dict[str, object], path: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    print(rendered, end="")
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    check = sub.add_parser("check")
    check.add_argument("--evidence", type=Path)
    compare = sub.add_parser("compare")
    compare.add_argument("--windows", type=Path, required=True)
    compare.add_argument("--linux", type=Path, required=True)
    compare.add_argument("--expected-revision", required=True)
    compare.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.mode == "check":
            payload = verify()
            evidence = args.evidence
        else:
            payload = compare_evidence(
                args.windows,
                args.linux,
                expected_revision=args.expected_revision,
            )
            evidence = args.evidence
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M3_MET_005_PASSIVE_REMAINDER_EVIDENCE_V1",
            "task_id": "M3-MET-005",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "source_revision": _git_revision(),
            "task_complete": False,
            "implementation_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        evidence = getattr(args, "evidence", None)
        code = 2
    _write(payload, evidence)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
