#!/usr/bin/env python3
"""M3-MET-008 exact P1 fusion remainder qualification evidence."""

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
FUSION_SUBJECT_ID = "67777777-7777-4777-8777-777777777777"
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


def _identity(prefix: str) -> dict[str, object]:
    return {
        f"{prefix}_id": f"{prefix}-id",
        f"{prefix}_version": "1.0.0",
        f"{prefix}_hash": HASH_A,
    }


def _quality_sample(
    *,
    domain: str,
    fused_field: str,
    fused: list[float],
    reference_field: str,
    reference: list[float],
) -> dict[str, object]:
    return {
        "reference_match_accepted": True,
        "error_domain": domain,
        "fused_track_valid": True,
        "fusion_provenance_resolved": True,
        "association_resolved": True,
        "source_member_ids": ["RADAR:track-1", "IRST:track-9"],
        fused_field: fused,
        reference_field: reference,
    }


def _handover_event(
    event_id: str,
    *,
    preserved: bool,
    qualified: bool = True,
) -> dict[str, object]:
    return {
        "handover_event_id": event_id,
        "reference_target_id": "target-1",
        "pre_fused_track_id": f"{event_id}-pre",
        "post_fused_track_id": f"{event_id}-post",
        "handover_time_us": 2_000_000,
        "identity_preserved": preserved,
        "handover_profile_id": "handover-profile",
        "handover_profile_version": "1.0.0",
        "handover_profile_hash": HASH_A,
        "qualification_status": "QUALIFIED" if qualified else "REJECTED",
        "association_resolved": True,
        "fusion_provenance_resolved": True,
    }


def _golden_inputs(system_type: str) -> dict[str, dict[str, object]]:
    return {
        "P1-FUS-001": {
            "system_type": system_type,
            **_identity("reference_match_quality_profile"),
            "samples": [
                _quality_sample(
                    domain="POSITION_3D",
                    fused_field="fused_track_position_ecef_m",
                    fused=[3.0, 4.0, 0.0],
                    reference_field="reference_target_position_ecef_m",
                    reference=[0.0, 0.0, 0.0],
                ),
                _quality_sample(
                    domain="POSITION_3D",
                    fused_field="fused_track_position_ecef_m",
                    fused=[0.0, 0.0, 13.0],
                    reference_field="reference_target_position_ecef_m",
                    reference=[0.0, 0.0, 0.0],
                ),
            ],
        },
        "P1-FUS-002": {
            "system_type": system_type,
            **_identity("reference_match_quality_profile"),
            "samples": [
                _quality_sample(
                    domain="VELOCITY_3D",
                    fused_field="fused_track_velocity_ecef_mps",
                    fused=[1.0, 0.0, 0.0],
                    reference_field="reference_target_velocity_ecef_mps",
                    reference=[0.0, 0.0, 0.0],
                ),
                _quality_sample(
                    domain="VELOCITY_3D",
                    fused_field="fused_track_velocity_ecef_mps",
                    fused=[0.0, 3.0, 0.0],
                    reference_field="reference_target_velocity_ecef_mps",
                    reference=[0.0, 0.0, 0.0],
                ),
            ],
        },
        "P1-FUS-003": {
            "system_type": system_type,
            "fused_update_id": "fused-update-1",
            "fused_state_effective_time_us": 5_000_000,
            "provenance_source_updates": [
                {
                    "source_id": "RADAR",
                    "sequence": 10,
                    "source_update_id": "src-radar-10",
                    "source_update_effective_time_us": 3_000_000,
                },
                {
                    "source_id": "IRST",
                    "sequence": 20,
                    "source_update_id": "src-irst-20",
                    "source_update_effective_time_us": 4_000_000,
                },
                {
                    "source_id": "EO",
                    "sequence": 30,
                    "source_update_id": "src-future-30",
                    "source_update_effective_time_us": 6_000_000,
                },
            ],
        },
        "P1-FUS-004": {
            "system_type": system_type,
            **_identity("opportunity_profile"),
            "fusion_provenance_resolved": True,
            "association_resolved": True,
            "fused_opportunity_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 10_000_000}
            ],
            "fused_track_valid_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 4_000_000},
                {"start_session_time_us": 6_000_000, "end_session_time_us": 10_000_000},
            ],
        },
        "P1-FUS-005": {
            "system_type": system_type,
            "profile": {"duplicate_persistence_s": 1.0},
            "fusion_provenance_resolved": True,
            "association_resolved": True,
            "eligible_target_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 10_000_000}
            ],
            "duplicate_episode_intervals": [
                {"start_session_time_us": 2_000_000, "end_session_time_us": 5_000_000},
                {"start_session_time_us": 7_000_000, "end_session_time_us": 7_500_000},
            ],
        },
        "P1-FUS-006": {
            "system_type": system_type,
            "source_track_membership": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 6_000_000,
                    "fused_track_id": "fused-1",
                    "source_track_id": "radar-1",
                    "reference_target_id": "target-1",
                    "membership_correct": True,
                },
                {
                    "start_session_time_us": 6_000_000,
                    "end_session_time_us": 8_000_000,
                    "fused_track_id": "fused-1",
                    "source_track_id": "irst-wrong",
                    "reference_target_id": "target-1",
                    "membership_correct": False,
                },
            ],
        },
        "P1-FUS-007": {
            "system_type": system_type,
            "handover_events": [
                _handover_event("handover-1", preserved=True),
                _handover_event("handover-2", preserved=False),
                _handover_event("handover-rejected", preserved=False, qualified=False),
            ],
        },
        "P1-FUS-008": {
            "system_type": system_type,
            "handover_event_id": "handover-jump-1",
            "reference_target_id": "target-1",
            "pre_fused_track_id": "fused-pre",
            "post_fused_track_id": "fused-post",
            "handover_time_us": 2_000_000,
            "qualification_status": "QUALIFIED",
            **_identity("handover_profile"),
            "pre_handover_state_time_us": 1_000_000,
            "fused_position_before": [0.0, 0.0, 0.0],
            "fused_velocity_before": [10.0, 0.0, 0.0],
            "fused_position_after": [130.0, 0.0, 0.0],
            "profile": {"max_propagation_age_us": 2_000_000},
        },
    }


def _instance(output: Mapping[str, object]) -> Mapping[str, object]:
    raw = output.get("instances")
    if not isinstance(raw, list) or len(raw) != 1 or not isinstance(raw[0], dict):
        raise ValueError("expected one metric instance")
    return cast(dict[str, object], raw[0])


def _upstream(code: str) -> tuple[tuple[str, str], ...]:
    if code in {"P1-FUS-001", "P1-FUS-002"}:
        return (("P1-QA-005", "5" * 64),)
    return ()


def _direct_output(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
    code: str,
    payload: Mapping[str, object],
) -> dict[str, object]:
    from tpaa_metric.catalog_engine import (
        M2MetricPluginRequest,
        validate_m2_runtime_output,
    )
    from tpaa_metric.m3_fusion_operators import M3_FUSION_OPERATOR_IMPLEMENTATIONS

    definition = plan.definition(code)
    _plugin_id, plugin = registry.resolve(
        definition.algorithm_id,
        definition.algorithm_version,
    )
    request = M2MetricPluginRequest(
        definition=definition,
        input_payload=payload,
        upstream_result_hashes=_upstream(code),
        operators={
            operator_id: M3_FUSION_OPERATOR_IMPLEMENTATIONS[operator_id]
            for operator_id in definition.operator_bindings
        },
    )
    output = dict(plugin(request))
    validate_m2_runtime_output(definition, payload, output)
    return output


def _direct_outputs(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
    inputs: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    from tpaa_metric.m3_fusion import M3_FUS_CODES

    return {
        code: _direct_output(plan, registry, code, inputs[code])
        for code in M3_FUS_CODES
    }


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"expected finite numeric value, got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"expected finite numeric value, got {value!r}")
    return result


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_metric import CatalogMetricEngine, MetricPluginRegistry
    from tpaa_metric.m3_fusion import (
        M3_FUS_ALLOWED_SYSTEM_TYPES,
        M3_FUS_CODES,
        register_m3_fusion_plugins,
    )
    from tpaa_metric.m3_fusion_operators import M3_FUSION_OPERATOR_IMPLEMENTATIONS
    from tpaa_metric.m3_general_engine import build_m3_metric_execution_plan
    from tpaa_metric.operators import M2_OPERATOR_IMPLEMENTATIONS
    from tpaa_metric.qa_foundation import register_m2_qa_plugins
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
    fusion = subjects[FUSION_SUBJECT_ID]
    negative = subjects[NEGATIVE_SUBJECT_ID]
    fusion_app = project_m3_family_applicability(
        world,
        family_code="P1-FUS-*",
        mission_system_instance_id=FUSION_SUBJECT_ID,
    )
    negative_app = project_m3_family_applicability(
        world,
        family_code="P1-FUS-*",
        mission_system_instance_id=NEGATIVE_SUBJECT_ID,
    )

    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    definitions = tuple(
        sorted(
            (
                definition
                for definition in plan.definitions
                if definition.metric_code in M3_FUS_CODES
            ),
            key=lambda definition: definition.metric_code,
        )
    )
    registry = MetricPluginRegistry()
    register_m2_qa_plugins(plan, registry)
    register_m3_fusion_plugins(plan, registry)

    positive_inputs = _golden_inputs(fusion.system_type)
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
    engine_inputs: dict[str, Mapping[str, object]] = {
        **positive_inputs,
        "P1-QA-005": qa_input,
    }
    engine = CatalogMetricEngine(
        plan,
        registry,
        operator_implementations=M3_FUSION_OPERATOR_IMPLEMENTATIONS,
    )
    first = engine.execute(engine_inputs, metric_codes=M3_FUS_CODES)
    replay = engine.execute(engine_inputs, metric_codes=M3_FUS_CODES)
    direct = _direct_outputs(plan, registry, positive_inputs)
    direct_replay = _direct_outputs(plan, registry, positive_inputs)

    negative_inputs: dict[str, dict[str, object]] = {
        code: {"system_type": negative.system_type}
        for code in M3_FUS_CODES
    }
    negative_engine_inputs: dict[str, Mapping[str, object]] = {
        **negative_inputs,
        "P1-QA-005": qa_input,
    }
    negative_batch = engine.execute(
        negative_engine_inputs,
        metric_codes=M3_FUS_CODES,
    )
    negative_replay = engine.execute(
        negative_engine_inputs,
        metric_codes=M3_FUS_CODES,
    )
    negative_direct = _direct_outputs(plan, registry, negative_inputs)

    rejected_inputs = _golden_inputs("FUSION")
    rejected_rows = rejected_inputs["P1-FUS-001"]["samples"]
    if not isinstance(rejected_rows, list):
        raise ValueError("quality rows invalid")
    for row in rejected_rows:
        if not isinstance(row, dict):
            raise ValueError("quality row invalid")
        row["reference_match_accepted"] = False
    rejected_quality = _direct_output(
        plan,
        registry,
        "P1-FUS-001",
        rejected_inputs["P1-FUS-001"],
    )

    stale_jump_inputs = _golden_inputs("FUSION")["P1-FUS-008"]
    stale_jump_inputs["pre_handover_state_time_us"] = 0
    stale_jump_inputs["profile"] = {"max_propagation_age_us": 1_000_000}
    stale_jump = _direct_output(
        plan,
        registry,
        "P1-FUS-008",
        stale_jump_inputs,
    )

    fus_records = tuple(
        record for record in first.records if record.metric_code in M3_FUS_CODES
    )
    negative_records = tuple(
        record
        for record in negative_batch.records
        if record.metric_code in M3_FUS_CODES
    )
    golden_numeric = {
        code: _number(_instance(direct[code]).get("value_numeric"))
        for code in M3_FUS_CODES
    }
    negative_outputs_exact = all(
        output.get("applicable") is False and output.get("instances") == []
        for output in negative_direct.values()
    )
    cv = M3_FUSION_OPERATOR_IMPLEMENTATIONS["CV_PROPAGATION_V1"]
    cv_result = cv(
        [0.0, 1.0, 2.0],
        [10.0, 20.0, 30.0],
        start_time_us=1_000_000,
        end_time_us=1_500_000,
        max_propagation_age_us=1_000_000,
    )

    acceptance = {
        "fusion_remainder_exact_8": (
            tuple(item.metric_code for item in definitions) == M3_FUS_CODES
        ),
        "fusion_family_exact": (
            {item.family for item in definitions} == {"SENSOR_FUSION"}
        ),
        "system_type_exact_fusion": all(
            item.applicability.applicability_mode == "SYSTEM_TYPE_EXACT"
            and item.applicability.allowed_system_types
            == M3_FUS_ALLOWED_SYSTEM_TYPES
            for item in definitions
        ),
        "world_fusion_applicable": (
            fusion_app.applicable and fusion.system_type == "FUSION"
        ),
        "world_radar_negative": (
            not negative_app.applicable and negative.system_type == "RADAR"
        ),
        "single_catalog_engine_dispatch": (
            len(fus_records) == 8
            and {record.plugin_id for record in fus_records}
            == {f"m3-fusion-remainder:{code}:v1" for code in M3_FUS_CODES}
        ),
        "qa_005_dependency_integrated": "P1-QA-005" in first.metric_codes,
        "fusion_execution_exact_8": len(fus_records) == 8,
        "non_applicable_execution_exact_8": (
            len(negative_records) == 8 and negative_outputs_exact
        ),
        "golden_position_rmse": math.isclose(
            golden_numeric["P1-FUS-001"],
            math.sqrt(97.0),
        ),
        "golden_velocity_rmse": math.isclose(
            golden_numeric["P1-FUS-002"],
            math.sqrt(5.0),
        ),
        "golden_fusion_latency_1s": golden_numeric["P1-FUS-003"] == 1.0,
        "golden_fused_continuity_0_8": (
            golden_numeric["P1-FUS-004"] == 0.8
        ),
        "golden_duplicate_suppression_0_7": math.isclose(
            golden_numeric["P1-FUS-005"],
            0.7,
        ),
        "golden_fusion_association_0_75": (
            golden_numeric["P1-FUS-006"] == 0.75
        ),
        "golden_handover_continuity_0_5": (
            golden_numeric["P1-FUS-007"] == 0.5
        ),
        "golden_handover_jump_120m": (
            golden_numeric["P1-FUS-008"] == 120.0
        ),
        "reference_quality_rejection_is_na": (
            _instance(rejected_quality).get("status") == "N_A"
        ),
        "stale_handover_state_is_na": (
            _instance(stale_jump).get("status") == "N_A"
        ),
        "cv_propagation_v1_implemented": cv_result == (5.0, 11.0, 17.0),
        "m2_operator_map_unchanged": (
            "CV_PROPAGATION_V1" not in M2_OPERATOR_IMPLEMENTATIONS
        ),
        "engine_replay_exact": first == replay,
        "negative_replay_exact": negative_batch == negative_replay,
        "plugin_replay_exact": direct == direct_replay,
    }
    failed = sorted(key for key, passed in acceptance.items() if not bool(passed))

    logical_product = {
        "metric_codes": list(M3_FUS_CODES),
        "allowed_system_types": list(M3_FUS_ALLOWED_SYSTEM_TYPES),
        "world_subjects": {
            "FUSION": fusion.mission_system_instance_id,
            "negative_RADAR": negative.mission_system_instance_id,
        },
        "golden_numeric": golden_numeric,
        "fusion_record_hashes": [
            [record.metric_code, record.logical_hash]
            for record in fus_records
        ],
        "negative_record_hashes": [
            [record.metric_code, record.logical_hash]
            for record in negative_records
        ],
        "execution_logical_hash": first.logical_hash,
        "negative_execution_logical_hash": negative_batch.logical_hash,
    }
    return {
        "schema": "TPAA_M3_MET_008_FUSION_REMAINDER_EVIDENCE_V1",
        "task_id": "M3-MET-008",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": _git_revision(),
        "task_complete": not failed,
        "implementation_complete": not failed,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "exact_fusion_remainder_8": True,
            "shared_catalog_engine": True,
            "system_type_exact_fusion_only": True,
            "cv_propagation_v1_implemented_without_m2_map_change": True,
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
        "logical_product_equal": (
            windows.get("logical_product") == linux.get("logical_product")
        ),
        "acceptance_equal": windows.get("acceptance") == linux.get("acceptance"),
        "failed_acceptance_empty": (
            windows.get("failed_acceptance") == []
            and linux.get("failed_acceptance") == []
        ),
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    return {
        "schema": "TPAA_M3_MET_008_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": "M3-MET-008",
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
            "schema": "TPAA_M3_MET_008_FUSION_REMAINDER_EVIDENCE_V1",
            "task_id": "M3-MET-008",
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
