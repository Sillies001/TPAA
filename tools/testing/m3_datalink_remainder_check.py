#!/usr/bin/env python3
"""M3-MET-007 exact P1 datalink remainder qualification evidence."""

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
DATALINK_SUBJECT_ID = "66666666-6666-4666-8666-666666666666"
NEGATIVE_SUBJECT_ID = "68888888-8888-4888-8888-888888888888"
HASH_A = "a" * 64
HASH_B = "b" * 64


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


def _identity(prefix: str, digest: str = HASH_A) -> dict[str, object]:
    return {
        f"{prefix}_id": f"{prefix}-id",
        f"{prefix}_version": "1.0.0",
        f"{prefix}_hash": digest,
    }


def _domain() -> dict[str, int]:
    return {"minimum": 0, "maximum": 15, "modulus": 16}


def _quality_sample(
    *,
    domain: str,
    remote_field: str,
    remote: list[float],
    reference_field: str,
    reference: list[float],
) -> dict[str, object]:
    return {
        "reference_match_accepted": True,
        "error_domain": domain,
        "remote_track_valid": True,
        "association_resolved": True,
        "link_endpoint_id": "link-1",
        remote_field: remote,
        reference_field: reference,
    }


def _golden_inputs(system_type: str) -> dict[str, dict[str, object]]:
    return {
        "P1-DL-001": {
            "system_type": system_type,
            "link_endpoint_id": "link-1",
            "message_send_time_us": 1_000_000,
            "message_receive_time_us": 2_500_000,
        },
        "P1-DL-002": {
            "system_type": system_type,
            "profile": {
                "min_message_count": 5,
                "max_gap_us": 1_000_000,
            },
            "message_latency_series": [
                {"session_time_us": 0, "message_latency_us": 100_000.0},
                {"session_time_us": 100_000, "message_latency_us": 110_000.0},
                {"session_time_us": 200_000, "message_latency_us": 130_000.0},
                {"session_time_us": 300_000, "message_latency_us": 120_000.0},
                {"session_time_us": 400_000, "message_latency_us": 500_000.0},
            ],
        },
        "P1-DL-003": {
            "system_type": system_type,
            "sequence_epochs": [
                {
                    "sequence_epoch_id": "epoch-loss",
                    "link_endpoint_id": "link-1",
                    "expected_sequence_domain": _domain(),
                    "observed_sequence_positions": [14, 15, 1, 2],
                }
            ],
        },
        "P1-DL-004": {
            "system_type": system_type,
            "sequence_epochs": [
                {
                    "sequence_epoch_id": "epoch-order",
                    "link_endpoint_id": "link-1",
                    "expected_sequence_domain": _domain(),
                    "received_messages": [
                        {"receive_order": 1, "sequence_position": 10},
                        {"receive_order": 2, "sequence_position": 12},
                        {"receive_order": 3, "sequence_position": 11},
                        {"receive_order": 4, "sequence_position": 13},
                    ],
                }
            ],
        },
        "P1-DL-005": {
            "system_type": system_type,
            "link_endpoint_id": "link-1",
            "remote_track_valid": True,
            "remote_track_effective_time_us": 2_000_000,
            "local_use_time_us": 4_500_000,
        },
        "P1-DL-006": {
            "system_type": system_type,
            **_identity("reference_match_quality_profile"),
            "samples": [
                _quality_sample(
                    domain="POSITION_3D",
                    remote_field="remote_track_position_ecef_m",
                    remote=[3.0, 4.0, 0.0],
                    reference_field="reference_target_position_ecef_m",
                    reference=[0.0, 0.0, 0.0],
                ),
                _quality_sample(
                    domain="POSITION_3D",
                    remote_field="remote_track_position_ecef_m",
                    remote=[0.0, 0.0, 13.0],
                    reference_field="reference_target_position_ecef_m",
                    reference=[0.0, 0.0, 0.0],
                ),
            ],
        },
        "P1-DL-007": {
            "system_type": system_type,
            **_identity("reference_match_quality_profile", HASH_B),
            "samples": [
                _quality_sample(
                    domain="VELOCITY_3D",
                    remote_field="remote_track_velocity_ecef_mps",
                    remote=[1.0, 0.0, 0.0],
                    reference_field="reference_target_velocity_ecef_mps",
                    reference=[0.0, 0.0, 0.0],
                ),
                _quality_sample(
                    domain="VELOCITY_3D",
                    remote_field="remote_track_velocity_ecef_mps",
                    remote=[0.0, 3.0, 0.0],
                    reference_field="reference_target_velocity_ecef_mps",
                    reference=[0.0, 0.0, 0.0],
                ),
            ],
        },
        "P1-DL-008": {
            "system_type": system_type,
            **_identity("opportunity_profile"),
            "link_endpoint_id": "link-1",
            "remote_track_opportunity_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 10_000_000}
            ],
            "remote_track_valid_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 4_000_000},
                {"start_session_time_us": 6_000_000, "end_session_time_us": 10_000_000},
            ],
        },
    }


def _instance(output: Mapping[str, object]) -> Mapping[str, object]:
    raw = output.get("instances")
    if not isinstance(raw, list) or len(raw) != 1 or not isinstance(raw[0], dict):
        raise ValueError("expected one metric instance")
    return cast(dict[str, object], raw[0])


def _upstream(code: str) -> tuple[tuple[str, str], ...]:
    if code == "P1-DL-002":
        return (("P1-DL-001", "1" * 64),)
    if code in {"P1-DL-006", "P1-DL-007"}:
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
    from tpaa_metric.m3_datalink_operators import (
        M3_DATALINK_OPERATOR_IMPLEMENTATIONS,
    )

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
            operator_id: M3_DATALINK_OPERATOR_IMPLEMENTATIONS[operator_id]
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
    from tpaa_metric.m3_datalink import M3_DL_CODES

    return {
        code: _direct_output(plan, registry, code, inputs[code])
        for code in M3_DL_CODES
    }


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"expected finite numeric value, got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"expected finite numeric value, got {value!r}")
    return result


def _negative_latency_rejected(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
) -> bool:
    payload = _golden_inputs("DATALINK")["P1-DL-001"]
    payload["message_receive_time_us"] = 999_999
    try:
        _direct_output(plan, registry, "P1-DL-001", payload)
    except ValueError as exc:
        return "M3_DL_NEGATIVE_MESSAGE_LATENCY" in str(exc)
    return False


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_metric import CatalogMetricEngine, MetricPluginRegistry
    from tpaa_metric.m3_datalink import (
        M3_DL_ALLOWED_SYSTEM_TYPES,
        M3_DL_CODES,
        register_m3_datalink_plugins,
    )
    from tpaa_metric.m3_datalink_operators import (
        M3_DATALINK_OPERATOR_IMPLEMENTATIONS,
    )
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
    datalink = subjects[DATALINK_SUBJECT_ID]
    negative = subjects[NEGATIVE_SUBJECT_ID]
    datalink_app = project_m3_family_applicability(
        world,
        family_code="P1-DL-*",
        mission_system_instance_id=DATALINK_SUBJECT_ID,
    )
    negative_app = project_m3_family_applicability(
        world,
        family_code="P1-DL-*",
        mission_system_instance_id=NEGATIVE_SUBJECT_ID,
    )

    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    definitions = tuple(
        sorted(
            (
                definition
                for definition in plan.definitions
                if definition.metric_code in M3_DL_CODES
            ),
            key=lambda definition: definition.metric_code,
        )
    )
    registry = MetricPluginRegistry()
    register_m2_qa_plugins(plan, registry)
    register_m3_datalink_plugins(plan, registry)

    positive_inputs = _golden_inputs(datalink.system_type)
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
        operator_implementations=M3_DATALINK_OPERATOR_IMPLEMENTATIONS,
    )
    first = engine.execute(engine_inputs, metric_codes=M3_DL_CODES)
    replay = engine.execute(engine_inputs, metric_codes=M3_DL_CODES)
    direct = _direct_outputs(plan, registry, positive_inputs)
    direct_replay = _direct_outputs(plan, registry, positive_inputs)

    negative_inputs: dict[str, dict[str, object]] = {
        code: {"system_type": negative.system_type}
        for code in M3_DL_CODES
    }
    negative_engine_inputs: dict[str, Mapping[str, object]] = {
        **negative_inputs,
        "P1-QA-005": qa_input,
    }
    negative_batch = engine.execute(
        negative_engine_inputs,
        metric_codes=M3_DL_CODES,
    )
    negative_replay = engine.execute(
        negative_engine_inputs,
        metric_codes=M3_DL_CODES,
    )
    negative_direct = _direct_outputs(plan, registry, negative_inputs)

    jitter_gap_inputs = _golden_inputs("DATALINK")
    jitter_rows = jitter_gap_inputs["P1-DL-002"]["message_latency_series"]
    if not isinstance(jitter_rows, list) or not isinstance(jitter_rows[-1], dict):
        raise ValueError("jitter rows invalid")
    jitter_rows[-1]["session_time_us"] = 2_000_000
    jitter_gap = _direct_output(
        plan,
        registry,
        "P1-DL-002",
        jitter_gap_inputs["P1-DL-002"],
    )

    rejected_quality_inputs = _golden_inputs("DATALINK")
    rejected_rows = rejected_quality_inputs["P1-DL-006"]["samples"]
    if not isinstance(rejected_rows, list):
        raise ValueError("quality rows invalid")
    for row in rejected_rows:
        if not isinstance(row, dict):
            raise ValueError("quality row invalid")
        row["reference_match_accepted"] = False
    rejected_quality = _direct_output(
        plan,
        registry,
        "P1-DL-006",
        rejected_quality_inputs["P1-DL-006"],
    )

    dl_records = tuple(
        record for record in first.records if record.metric_code in M3_DL_CODES
    )
    negative_dl_records = tuple(
        record
        for record in negative_batch.records
        if record.metric_code in M3_DL_CODES
    )
    golden_numeric = {
        code: _number(_instance(direct[code]).get("value_numeric"))
        for code in M3_DL_CODES
    }
    negative_outputs_exact = all(
        output.get("applicable") is False and output.get("instances") == []
        for output in negative_direct.values()
    )
    mad = M3_DATALINK_OPERATOR_IMPLEMENTATIONS["MAD_V1"]
    mad_result = mad([100_000.0, 110_000.0, 130_000.0, 120_000.0, 500_000.0])

    acceptance = {
        "datalink_remainder_exact_8": (
            tuple(item.metric_code for item in definitions) == M3_DL_CODES
        ),
        "datalink_family_exact": (
            {item.family for item in definitions} == {"DATALINK"}
        ),
        "system_type_exact_datalink": all(
            item.applicability.applicability_mode == "SYSTEM_TYPE_EXACT"
            and item.applicability.allowed_system_types == M3_DL_ALLOWED_SYSTEM_TYPES
            for item in definitions
        ),
        "world_datalink_applicable": (
            datalink_app.applicable and datalink.system_type == "DATALINK"
        ),
        "world_radar_negative": (
            not negative_app.applicable and negative.system_type == "RADAR"
        ),
        "single_catalog_engine_dispatch": (
            len(dl_records) == 8
            and {record.plugin_id for record in dl_records}
            == {f"m3-datalink-remainder:{code}:v1" for code in M3_DL_CODES}
        ),
        "qa_005_dependency_integrated": "P1-QA-005" in first.metric_codes,
        "dl_001_dependency_integrated": (
            any(
                code == "P1-DL-001"
                for code, _digest in next(
                    record.upstream_result_hashes
                    for record in dl_records
                    if record.metric_code == "P1-DL-002"
                )
            )
        ),
        "datalink_execution_exact_8": len(dl_records) == 8,
        "non_applicable_execution_exact_8": (
            len(negative_dl_records) == 8 and negative_outputs_exact
        ),
        "golden_message_latency_1_5s": golden_numeric["P1-DL-001"] == 1.5,
        "golden_message_jitter_mad_0_01s": (
            golden_numeric["P1-DL-002"] == 0.01
        ),
        "golden_message_loss_wrap_0_2": (
            golden_numeric["P1-DL-003"] == 0.2
        ),
        "golden_out_of_order_rate_0_25": (
            golden_numeric["P1-DL-004"] == 0.25
        ),
        "golden_remote_track_age_2_5s": (
            golden_numeric["P1-DL-005"] == 2.5
        ),
        "golden_position_rmse": math.isclose(
            golden_numeric["P1-DL-006"],
            math.sqrt(97.0),
        ),
        "golden_velocity_rmse": math.isclose(
            golden_numeric["P1-DL-007"],
            math.sqrt(5.0),
        ),
        "golden_remote_track_continuity_0_8": (
            golden_numeric["P1-DL-008"] == 0.8
        ),
        "jitter_gap_is_na": _instance(jitter_gap).get("status") == "N_A",
        "reference_quality_rejection_is_na": (
            _instance(rejected_quality).get("status") == "N_A"
        ),
        "negative_latency_rejected": _negative_latency_rejected(plan, registry),
        "mad_v1_implemented": mad_result == 10_000.0,
        "m2_operator_map_unchanged": (
            tuple(M2_OPERATOR_IMPLEMENTATIONS)
            == (
                "CIRCULAR_MEAN_V1",
                "DERIVATIVE_LLS_V1",
                "LINEAR_INTERPOLATION_V1",
                "MEAN_V1",
                "MEDIAN_V1",
                "QUANTILE_HF7_V1",
                "RMS_V1",
                "WRAP_PI_V1",
            )
            and "MAD_V1" not in M2_OPERATOR_IMPLEMENTATIONS
        ),
        "engine_replay_exact": first == replay,
        "negative_replay_exact": negative_batch == negative_replay,
        "plugin_replay_exact": direct == direct_replay,
    }
    failed = sorted(key for key, passed in acceptance.items() if not bool(passed))

    logical_product = {
        "metric_codes": list(M3_DL_CODES),
        "allowed_system_types": list(M3_DL_ALLOWED_SYSTEM_TYPES),
        "world_subjects": {
            "DATALINK": datalink.mission_system_instance_id,
            "negative_RADAR": negative.mission_system_instance_id,
        },
        "golden_numeric": golden_numeric,
        "datalink_record_hashes": [
            [record.metric_code, record.logical_hash]
            for record in dl_records
        ],
        "negative_record_hashes": [
            [record.metric_code, record.logical_hash]
            for record in negative_dl_records
        ],
        "execution_logical_hash": first.logical_hash,
        "negative_execution_logical_hash": negative_batch.logical_hash,
    }
    return {
        "schema": "TPAA_M3_MET_007_DATALINK_REMAINDER_EVIDENCE_V1",
        "task_id": "M3-MET-007",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": _git_revision(),
        "task_complete": not failed,
        "implementation_complete": not failed,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "exact_datalink_remainder_8": True,
            "shared_catalog_engine": True,
            "system_type_exact_datalink_only": True,
            "mad_v1_implemented_without_m2_map_change": True,
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
        "schema": "TPAA_M3_MET_007_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": "M3-MET-007",
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
            "schema": "TPAA_M3_MET_007_DATALINK_REMAINDER_EVIDENCE_V1",
            "task_id": "M3-MET-007",
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
