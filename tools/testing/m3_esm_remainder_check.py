#!/usr/bin/env python3
"""M3-MET-006 exact P1 ESM remainder qualification evidence."""

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
RWR_SUBJECT_ID = "64444444-4444-4444-8444-444444444444"
ESM_SUBJECT_ID = "65555555-5555-4555-8555-555555555555"
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


def _golden_inputs(system_type: str) -> dict[str, dict[str, object]]:
    taxonomy: dict[str, object] = {
        "taxonomy_id": "esm-taxonomy",
        "taxonomy_version": "1.0.0",
        "taxonomy_hash": HASH_A,
        "canonical_labels": ["FRIEND", "FOE", "UNKNOWN"],
        "alias_map": {"hostile": "FOE"},
        "unknown_label": "UNKNOWN",
    }
    return {
        "P1-ESM-001": {
            "system_type": system_type,
            **_identity("opportunity_profile"),
            **_identity("confirmation_profile"),
            "emitter_opportunity_intervals": [
                {
                    "detection_opportunity_id": "opp-1",
                    "reference_emitter_id": "emitter-1",
                    "start_session_time_us": 0,
                    "end_session_time_us": 2_000_000,
                },
                {
                    "detection_opportunity_id": "opp-2",
                    "reference_emitter_id": "emitter-2",
                    "start_session_time_us": 2_000_000,
                    "end_session_time_us": 4_000_000,
                },
                {
                    "detection_opportunity_id": "opp-3",
                    "reference_emitter_id": "emitter-3",
                    "start_session_time_us": 4_000_000,
                    "end_session_time_us": 6_000_000,
                },
            ],
            "confirmation_events": [
                {
                    "detection_confirmation_event_id": "confirm-1",
                    "detection_opportunity_id": "opp-1",
                    "reference_emitter_id": "emitter-1",
                },
                {
                    "detection_confirmation_event_id": "confirm-3",
                    "detection_opportunity_id": "opp-3",
                    "reference_emitter_id": "emitter-3",
                },
            ],
        },
        "P1-ESM-002": {
            "system_type": system_type,
            **_identity("reference_match_quality_profile"),
            "samples": [
                {
                    "reported_bearing_rad": math.pi - 0.1,
                    "reference_bearing_rad": -math.pi + 0.1,
                    "reference_match_accepted": True,
                    "error_domain": "BEARING",
                },
                {
                    "reported_bearing_rad": 0.1,
                    "reference_bearing_rad": 0.0,
                    "reference_match_accepted": True,
                    "error_domain": "BEARING",
                },
            ],
        },
        "P1-ESM-003": {
            "system_type": system_type,
            **_identity("opportunity_profile"),
            **_identity("confirmation_profile"),
            "detection_opportunity_id": "opp-latency",
            "detection_confirmation_event_id": "confirm-latency",
            "opportunity_start_time_us": 1_000_000,
            "first_confirmed_detection_time_us": 2_500_000,
        },
        "P1-ESM-004": {
            "system_type": system_type,
            "association_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 6_000_000,
                    "esm_emitter_track_id": "esm-track-1",
                    "reference_emitter_id": "emitter-1",
                    "association_state": "CORRECT",
                },
                {
                    "start_session_time_us": 6_000_000,
                    "end_session_time_us": 8_000_000,
                    "esm_emitter_track_id": "esm-track-1",
                    "reference_emitter_id": "emitter-2",
                    "association_state": "WRONG",
                },
            ],
        },
        "P1-ESM-005": {
            "system_type": system_type,
            "reference_classification_taxonomy_id": "esm-taxonomy",
            "reference_classification_taxonomy_version": "1.0.0",
            "reference_classification_taxonomy_hash": HASH_A,
            "taxonomy": taxonomy,
            "classification_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 4_000_000,
                    "reported_emitter_class": "FRIEND",
                    "reference_emitter_class": "FRIEND",
                    "association_resolved": True,
                    "reference_quality_status": "VALID",
                },
                {
                    "start_session_time_us": 4_000_000,
                    "end_session_time_us": 6_000_000,
                    "reported_emitter_class": "hostile",
                    "reference_emitter_class": "FRIEND",
                    "association_resolved": True,
                    "reference_quality_status": "VALID",
                },
                {
                    "start_session_time_us": 6_000_000,
                    "end_session_time_us": 7_000_000,
                    "reported_emitter_class": "UNKNOWN",
                    "reference_emitter_class": "FOE",
                    "association_resolved": True,
                    "reference_quality_status": "VALID",
                },
            ],
        },
        "P1-ESM-006": {
            "system_type": system_type,
            **_identity("opportunity_profile"),
            "emitter_opportunity_intervals": [
                {"start_session_time_us": 0, "end_session_time_us": 10_000_000}
            ],
            "esm_track_valid_intervals": [
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
    from tpaa_metric.m3_air_operators import M3_AIR_OPERATOR_IMPLEMENTATIONS

    definition = plan.definition(code)
    _plugin_id, plugin = registry.resolve(
        definition.algorithm_id,
        definition.algorithm_version,
    )
    request = M2MetricPluginRequest(
        definition=definition,
        input_payload=payload,
        upstream_result_hashes=(),
        operators={
            operator_id: M3_AIR_OPERATOR_IMPLEMENTATIONS[operator_id]
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
    from tpaa_metric.m3_esm import M3_ESM_CODES

    return {
        code: _direct_output(plan, registry, code, inputs[code])
        for code in M3_ESM_CODES
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
    from tpaa_metric.m3_air_operators import M3_AIR_OPERATOR_IMPLEMENTATIONS
    from tpaa_metric.m3_esm import (
        M3_ESM_ALLOWED_SYSTEM_TYPES,
        M3_ESM_CODES,
        register_m3_esm_plugins,
    )
    from tpaa_metric.m3_general_engine import build_m3_metric_execution_plan
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
    rwr_subject = subjects[RWR_SUBJECT_ID]
    esm_subject = subjects[ESM_SUBJECT_ID]
    negative_subject = subjects[NEGATIVE_SUBJECT_ID]
    rwr_applicability = project_m3_family_applicability(
        world_inputs,
        family_code="P1-ESM-*",
        mission_system_instance_id=RWR_SUBJECT_ID,
    )
    esm_applicability = project_m3_family_applicability(
        world_inputs,
        family_code="P1-ESM-*",
        mission_system_instance_id=ESM_SUBJECT_ID,
    )
    negative_applicability = project_m3_family_applicability(
        world_inputs,
        family_code="P1-ESM-*",
        mission_system_instance_id=NEGATIVE_SUBJECT_ID,
    )

    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    definitions = tuple(
        sorted(
            (
                definition
                for definition in plan.definitions
                if definition.metric_code in M3_ESM_CODES
            ),
            key=lambda definition: definition.metric_code,
        )
    )
    registry = MetricPluginRegistry()
    register_m3_esm_plugins(plan, registry)
    engine = CatalogMetricEngine(
        plan,
        registry,
        operator_implementations=M3_AIR_OPERATOR_IMPLEMENTATIONS,
    )

    rwr_inputs = _golden_inputs(rwr_subject.system_type)
    esm_inputs = _golden_inputs(esm_subject.system_type)
    negative_inputs: dict[str, dict[str, object]] = {
        code: {"system_type": negative_subject.system_type}
        for code in M3_ESM_CODES
    }

    rwr_batch = engine.execute(rwr_inputs, metric_codes=M3_ESM_CODES)
    rwr_replay = engine.execute(rwr_inputs, metric_codes=M3_ESM_CODES)
    esm_batch = engine.execute(esm_inputs, metric_codes=M3_ESM_CODES)
    esm_replay = engine.execute(esm_inputs, metric_codes=M3_ESM_CODES)
    negative_batch = engine.execute(negative_inputs, metric_codes=M3_ESM_CODES)
    negative_replay = engine.execute(negative_inputs, metric_codes=M3_ESM_CODES)

    direct = _direct_outputs(plan, registry, rwr_inputs)
    direct_replay = _direct_outputs(plan, registry, rwr_inputs)
    negative_direct = _direct_outputs(plan, registry, negative_inputs)

    rejected_bearing = _golden_inputs(rwr_subject.system_type)["P1-ESM-002"]
    rejected_bearing["samples"] = [
        {
            "reference_match_accepted": False,
            "error_domain": "BEARING",
        }
    ]
    rejected_bearing_output = _direct_output(
        plan,
        registry,
        "P1-ESM-002",
        rejected_bearing,
    )

    golden_numeric = {
        code: _number(_instance(direct[code]).get("value_numeric"))
        for code in M3_ESM_CODES
    }
    classification_evidence = _instance(direct["P1-ESM-005"]).get("evidence")
    confusion_present = (
        isinstance(classification_evidence, Mapping)
        and "canonical_confusion_matrix_dwell_us" in classification_evidence
    )
    negative_outputs_exact = all(
        output.get("applicable") is False and output.get("instances") == []
        for output in negative_direct.values()
    )
    rejected_bearing_instance = _instance(rejected_bearing_output)

    acceptance = {
        "esm_remainder_exact_6": (
            tuple(item.metric_code for item in definitions) == M3_ESM_CODES
        ),
        "esm_family_exact": ({item.family for item in definitions} == {"RWR_ESM"}),
        "system_type_set_exact": all(
            item.applicability.applicability_mode == "SYSTEM_TYPE_SET"
            and item.applicability.allowed_system_types == M3_ESM_ALLOWED_SYSTEM_TYPES
            for item in definitions
        ),
        "world_rwr_applicable": (
            rwr_applicability.applicable and rwr_subject.system_type == "RWR"
        ),
        "world_esm_applicable": (
            esm_applicability.applicable and esm_subject.system_type == "ESM"
        ),
        "world_radar_negative": (
            not negative_applicability.applicable
            and negative_subject.system_type == "RADAR"
        ),
        "single_catalog_engine_dispatch": (
            len(rwr_batch.records) == 6
            and {
                record.plugin_id
                for record in rwr_batch.records
            }
            == {f"m3-esm-remainder:{code}:v1" for code in M3_ESM_CODES}
        ),
        "rwr_execution_exact_6_valid": all(
            _instance(output).get("status") == "VALID"
            for output in direct.values()
        ),
        "esm_execution_exact_6": len(esm_batch.records) == 6,
        "non_applicable_execution_exact_6": (
            len(negative_batch.records) == 6 and negative_outputs_exact
        ),
        "golden_detection_rate_2_of_3": math.isclose(
            golden_numeric["P1-ESM-001"],
            2.0 / 3.0,
        ),
        "golden_bearing_wrap_rmse": math.isclose(
            golden_numeric["P1-ESM-002"],
            math.sqrt(0.025),
            rel_tol=1e-12,
            abs_tol=1e-12,
        ),
        "golden_detection_latency_1_5s": (
            golden_numeric["P1-ESM-003"] == 1.5
        ),
        "golden_association_accuracy_0_75": (
            golden_numeric["P1-ESM-004"] == 0.75
        ),
        "golden_classification_accuracy_2_of_3": math.isclose(
            golden_numeric["P1-ESM-005"],
            2.0 / 3.0,
        ),
        "classification_confusion_evidence_present": confusion_present,
        "golden_track_continuity_0_8": (
            golden_numeric["P1-ESM-006"] == 0.8
        ),
        "reference_quality_rejection_is_na": (
            rejected_bearing_instance.get("status") == "N_A"
            and rejected_bearing_instance.get("value_numeric") is None
        ),
        "rwr_replay_exact": rwr_batch == rwr_replay,
        "esm_replay_exact": esm_batch == esm_replay,
        "negative_replay_exact": negative_batch == negative_replay,
        "plugin_replay_exact": direct == direct_replay,
    }
    failed = sorted(key for key, passed in acceptance.items() if not bool(passed))

    logical_product = {
        "metric_codes": list(M3_ESM_CODES),
        "allowed_system_types": list(M3_ESM_ALLOWED_SYSTEM_TYPES),
        "world_subjects": {
            "RWR": rwr_subject.mission_system_instance_id,
            "ESM": esm_subject.mission_system_instance_id,
            "negative_RADAR": negative_subject.mission_system_instance_id,
        },
        "golden_numeric": golden_numeric,
        "rwr_record_hashes": [
            [record.metric_code, record.logical_hash]
            for record in rwr_batch.records
        ],
        "esm_record_hashes": [
            [record.metric_code, record.logical_hash]
            for record in esm_batch.records
        ],
        "negative_record_hashes": [
            [record.metric_code, record.logical_hash]
            for record in negative_batch.records
        ],
        "rwr_execution_logical_hash": rwr_batch.logical_hash,
        "esm_execution_logical_hash": esm_batch.logical_hash,
        "negative_execution_logical_hash": negative_batch.logical_hash,
    }
    return {
        "schema": "TPAA_M3_MET_006_ESM_REMAINDER_EVIDENCE_V1",
        "task_id": "M3-MET-006",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": _git_revision(),
        "task_complete": not failed,
        "implementation_complete": not failed,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "exact_esm_remainder_6": True,
            "shared_catalog_engine": True,
            "system_type_set_rwr_esm_only": True,
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
        "schema": "TPAA_M3_MET_006_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": "M3-MET-006",
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
            "schema": "TPAA_M3_MET_006_ESM_REMAINDER_EVIDENCE_V1",
            "task_id": "M3-MET-006",
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
