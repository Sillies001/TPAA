#!/usr/bin/env python3
"""M3-MET-003 exact P1 TRK remainder qualification evidence."""

from __future__ import annotations

import argparse
import json
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
TRACK_SUBJECT_ID = "61111111-1111-4111-8111-111111111111"
NEGATIVE_SUBJECT_ID = "68888888-8888-4888-8888-888888888888"
HASH_A = "a" * 64


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


def _opportunity_identity() -> dict[str, object]:
    return {
        "detection_opportunity_id": "opp-001",
        "opportunity_profile_id": "opportunity-profile",
        "opportunity_profile_version": "1.0.0",
        "opportunity_profile_hash": HASH_A,
    }


def _golden_inputs(products: list[str]) -> dict[str, dict[str, object]]:
    reference_profile = {
        "reference_match_quality_profile_id": "reference-profile",
        "reference_match_quality_profile_version": "1.0.0",
        "reference_match_quality_profile_hash": HASH_A,
    }
    return {
        "P1-TRK-001": {
            "product_semantics": products,
            "first_confirmed_detection_time_us": 1_000_000,
            "stable_track_start_time_us": 2_500_000,
            "detection_confirmation_event_id": "confirm-001",
            "confirmation_profile_id": "confirm-profile",
            "confirmation_profile_version": "1.0.0",
            "confirmation_profile_hash": HASH_A,
            "profile": {
                "stable_track_persistence_s": 0.5,
                "max_gap_us": 500_000,
            },
        },
        "P1-TRK-002": {
            "product_semantics": products,
            **reference_profile,
            "samples": [
                {
                    "track_position_ecef_m": [3.0, 4.0, 0.0],
                    "reference_target_position_ecef_m": [0.0, 0.0, 0.0],
                    "reference_match_accepted": True,
                    "error_domain": "POSITION_3D",
                },
                {
                    "track_position_ecef_m": [0.0, 3.0, 4.0],
                    "reference_target_position_ecef_m": [0.0, 0.0, 0.0],
                    "reference_match_accepted": True,
                    "error_domain": "POSITION_3D",
                },
            ],
        },
        "P1-TRK-003": {
            "product_semantics": products,
            **reference_profile,
            "samples": [
                {
                    "track_velocity_ecef_mps": [2.0, 0.0, 0.0],
                    "reference_target_velocity_ecef_mps": [0.0, 0.0, 0.0],
                    "reference_match_accepted": True,
                    "error_domain": "VELOCITY_3D",
                },
                {
                    "track_velocity_ecef_mps": [0.0, 2.0, 0.0],
                    "reference_target_velocity_ecef_mps": [0.0, 0.0, 0.0],
                    "reference_match_accepted": True,
                    "error_domain": "VELOCITY_3D",
                },
            ],
        },
        "P1-TRK-004": {
            "product_semantics": products,
            **_opportunity_identity(),
            "evaluation_opportunity_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 10_000_000}
            ],
            "valid_track_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 4_000_000},
                {"start_session_time_us": 6_000_000, "end_session_time_us": 10_000_000},
            ],
        },
        "P1-TRK-005": {
            "product_semantics": products,
            **_opportunity_identity(),
            "opportunity_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 12_000_000}
            ],
            "valid_track_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 2_000_000},
                {
                    "start_session_time_us": 2_200_000,
                    "end_session_time_us": 4_000_000,
                },
                {"start_session_time_us": 6_000_000, "end_session_time_us": 8_000_000},
                {
                    "start_session_time_us": 10_000_000,
                    "end_session_time_us": 12_000_000,
                },
            ],
            "profile": {"drop_min_duration_s": 1.0},
        },
        "P1-TRK-006": {
            "product_semantics": products,
            **_opportunity_identity(),
            "profile": {
                "drop_min_duration_s": 1.0,
                "reacquisition_persistence_s": 0.5,
            },
            "reacquisition_events": [
                {
                    "detection_opportunity_id": "opp-001",
                    "track_drop_start_time_us": 0,
                    "reacquired_stable_track_time_us": 2_000_000,
                    "invalid_dwell_s": 1.5,
                    "stable_persistence_s": 0.5,
                },
                {
                    "detection_opportunity_id": "opp-001",
                    "track_drop_start_time_us": 10_000_000,
                    "reacquired_stable_track_time_us": 14_000_000,
                    "invalid_dwell_s": 3.0,
                    "stable_persistence_s": 0.5,
                },
            ],
        },
        "P1-TRK-007": {
            "product_semantics": products,
            "track_state_time_us": [2_000_000, 4_000_000, 6_000_000],
            "last_measurement_effective_time_us": [
                1_000_000,
                2_000_000,
                3_000_000,
            ],
        },
    }


def _instance(output: dict[str, object]) -> dict[str, object]:
    raw = output.get("instances")
    if not isinstance(raw, list) or len(raw) != 1 or not isinstance(raw[0], dict):
        raise ValueError("expected one metric instance")
    return cast(dict[str, object], raw[0])


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
    from tpaa_metric.m3_track import M3_TRK_CODES

    outputs: dict[str, dict[str, object]] = {}
    for code in M3_TRK_CODES:
        definition = plan.definition(code)
        _plugin_id, plugin = registry.resolve(
            definition.algorithm_id,
            definition.algorithm_version,
        )
        upstream = (
            (("P1-QA-005", "b" * 64),)
            if code in {"P1-TRK-002", "P1-TRK-003"}
            else ()
        )
        request = M2MetricPluginRequest(
            definition=definition,
            input_payload=inputs[code],
            upstream_result_hashes=upstream,
            operators={
                operator_id: M3_AIR_OPERATOR_IMPLEMENTATIONS[operator_id]
                for operator_id in definition.operator_bindings
            },
        )
        output = dict(plugin(request))
        validate_m2_runtime_output(definition, inputs[code], output)
        outputs[code] = output
    return outputs


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_metric import CatalogMetricEngine, MetricPluginRegistry
    from tpaa_metric.m3_air_operators import M3_AIR_OPERATOR_IMPLEMENTATIONS
    from tpaa_metric.m3_general_engine import build_m3_metric_execution_plan
    from tpaa_metric.m3_track import (
        M3_TRK_CODES,
        M3_TRK_REQUIRED_PRODUCT_SEMANTICS,
        register_m3_track_plugins,
    )
    from tpaa_metric.qa_foundation import register_m2_qa_plugins
    from tpaa_world.m3_mission_product_applicability import (
        load_m3_mission_product_inputs,
        project_m3_family_applicability,
    )

    world_inputs = load_m3_mission_product_inputs(
        MISSION_FIXTURE,
        authority_root=AUTHORITY_ROOT,
    )
    subjects = {
        subject.mission_system_instance_id: subject
        for subject in world_inputs.subjects
    }
    positive_subject = subjects[TRACK_SUBJECT_ID]
    negative_subject = subjects[NEGATIVE_SUBJECT_ID]
    positive_applicability = project_m3_family_applicability(
        world_inputs,
        family_code="P1-TRK-*",
        mission_system_instance_id=TRACK_SUBJECT_ID,
    )
    negative_applicability = project_m3_family_applicability(
        world_inputs,
        family_code="P1-TRK-*",
        mission_system_instance_id=NEGATIVE_SUBJECT_ID,
    )

    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    definitions = tuple(
        sorted(
            (
                definition
                for definition in plan.definitions
                if definition.metric_code in M3_TRK_CODES
            ),
            key=lambda definition: definition.metric_code,
        )
    )
    registry = MetricPluginRegistry()
    register_m2_qa_plugins(plan, registry)
    register_m3_track_plugins(plan, registry)

    positive_inputs = _golden_inputs(list(positive_subject.product_semantics))
    qa_input: dict[str, object] = {
        "samples": [
            {
                "measurement_time_us": 500_000,
                "left_truth_time_us": 0,
                "right_truth_time_us": 1_000_000,
                "profile.max_gap_us": 1_000_000,
            }
        ]
    }
    engine_inputs: dict[str, dict[str, object]] = {
        "P1-QA-005": qa_input,
        **positive_inputs,
    }
    engine = CatalogMetricEngine(
        plan,
        registry,
        operator_implementations=M3_AIR_OPERATOR_IMPLEMENTATIONS,
    )
    first = engine.execute(engine_inputs, metric_codes=M3_TRK_CODES)
    replay = engine.execute(engine_inputs, metric_codes=M3_TRK_CODES)

    direct = _direct_outputs(plan, registry, positive_inputs)
    direct_replay = _direct_outputs(plan, registry, positive_inputs)

    negative_inputs: dict[str, dict[str, object]] = {
        code: {
            "product_semantics": list(negative_subject.product_semantics),
        }
        for code in M3_TRK_CODES
    }
    negative_engine_inputs: dict[str, dict[str, object]] = {
        "P1-QA-005": qa_input,
        **negative_inputs,
    }
    negative_batch = engine.execute(
        negative_engine_inputs,
        metric_codes=M3_TRK_CODES,
    )
    negative_direct = _direct_outputs(plan, registry, negative_inputs)

    trk_records = tuple(
        record for record in first.records if record.metric_code in M3_TRK_CODES
    )
    negative_trk_records = tuple(
        record
        for record in negative_batch.records
        if record.metric_code in M3_TRK_CODES
    )
    golden_numeric = {
        code: _instance(direct[code]).get("value_numeric")
        for code in M3_TRK_CODES
    }
    negative_outputs_exact = all(
        output.get("applicable") is False and output.get("instances") == []
        for output in negative_direct.values()
    )

    acceptance = {
        "track_remainder_exact_7": (
            tuple(item.metric_code for item in definitions) == M3_TRK_CODES
        ),
        "track_family_exact": (
            {item.family for item in definitions} == {"TRACK_PERFORMANCE"}
        ),
        "product_applicability_contract_exact": all(
            item.applicability.applicability_mode == "PRODUCT_CAPABILITY"
            and item.applicability.required_product_semantics
            == M3_TRK_REQUIRED_PRODUCT_SEMANTICS
            for item in definitions
        ),
        "world_positive_local_track_product": (
            positive_applicability.applicable
            and positive_applicability.product_input_emitted
            and M3_TRK_REQUIRED_PRODUCT_SEMANTICS
            in positive_subject.product_semantics
        ),
        "world_negative_product_fails_closed": (
            not negative_applicability.applicable
            and not negative_applicability.product_input_emitted
            and M3_TRK_REQUIRED_PRODUCT_SEMANTICS
            not in negative_subject.product_semantics
        ),
        "single_catalog_engine_dispatch": (
            len(trk_records) == 7
            and {record.plugin_id for record in trk_records}
            == {f"m3-track-remainder:{code}:v1" for code in M3_TRK_CODES}
        ),
        "qa_005_dependency_integrated": (
            "P1-QA-005" in first.metric_codes
            and len(first.metric_codes) == 8
        ),
        "applicable_execution_exact_7": (
            {record.metric_code for record in trk_records} == set(M3_TRK_CODES)
            and all(
                _instance(output)["status"] == "VALID"
                for output in direct.values()
            )
        ),
        "non_applicable_execution_exact_7": (
            len(negative_trk_records) == 7 and negative_outputs_exact
        ),
        "runtime_contract_product_mode_enforced": negative_outputs_exact,
        "execution_replay_exact": first == replay,
        "plugin_replay_exact": direct == direct_replay,
        "golden_track_initiation_1_5s": golden_numeric["P1-TRK-001"] == 1.5,
        "golden_position_rmse_5m": golden_numeric["P1-TRK-002"] == 5.0,
        "golden_velocity_rmse_2mps": golden_numeric["P1-TRK-003"] == 2.0,
        "golden_continuity_0_8": golden_numeric["P1-TRK-004"] == 0.8,
        "golden_drop_count_2": golden_numeric["P1-TRK-005"] == 2.0,
        "golden_reacquisition_median_3s": golden_numeric["P1-TRK-006"] == 3.0,
        "golden_track_age_median_2s": golden_numeric["P1-TRK-007"] == 2.0,
    }
    failed = sorted(key for key, passed in acceptance.items() if not bool(passed))
    logical_product = {
        "metric_codes": list(M3_TRK_CODES),
        "required_product_semantics": M3_TRK_REQUIRED_PRODUCT_SEMANTICS,
        "positive_subject": {
            "mission_system_instance_id": positive_subject.mission_system_instance_id,
            "system_type": positive_subject.system_type,
            "product_semantics": list(positive_subject.product_semantics),
            "applicability_hash": positive_applicability.logical_hash,
        },
        "negative_subject": {
            "mission_system_instance_id": negative_subject.mission_system_instance_id,
            "system_type": negative_subject.system_type,
            "product_semantics": list(negative_subject.product_semantics),
            "applicability_hash": negative_applicability.logical_hash,
        },
        "execution_metric_codes": list(first.metric_codes),
        "golden_numeric": golden_numeric,
        "record_hashes": [
            [record.metric_code, record.logical_hash] for record in trk_records
        ],
        "negative_record_hashes": [
            [record.metric_code, record.logical_hash]
            for record in negative_trk_records
        ],
        "execution_logical_hash": first.logical_hash,
        "negative_execution_logical_hash": negative_batch.logical_hash,
    }
    return {
        "schema": "TPAA_M3_MET_003_TRACK_REMAINDER_EVIDENCE_V1",
        "task_id": "M3-MET-003",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": _git_revision(),
        "task_complete": not failed,
        "implementation_complete": not failed,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "exact_track_remainder_7": True,
            "shared_catalog_engine": True,
            "local_track_product_only": True,
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
        "schema": "TPAA_M3_MET_003_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": "M3-MET-003",
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
            "schema": "TPAA_M3_MET_003_TRACK_REMAINDER_EVIDENCE_V1",
            "task_id": "M3-MET-003",
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
