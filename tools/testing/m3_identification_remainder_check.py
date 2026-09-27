#!/usr/bin/env python3
"""M3-MET-004 exact P1 ID remainder qualification evidence."""

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
ID_SUBJECT_ID = "61111111-1111-4111-8111-111111111111"
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


def _taxonomy_fields() -> dict[str, object]:
    return {
        "reference_classification_taxonomy_id": "tax-v1",
        "reference_classification_taxonomy_version": "1.0.0",
        "reference_classification_taxonomy_hash": HASH_A,
        "taxonomy": {
            "taxonomy_id": "tax-v1",
            "taxonomy_version": "1.0.0",
            "taxonomy_hash": HASH_A,
            "canonical_labels": ["FRIEND", "HOSTILE", "UNKNOWN"],
            "alias_map": {"F": "FRIEND", "H": "HOSTILE"},
            "unknown_label": "UNKNOWN",
        },
    }


def _class_intervals() -> list[dict[str, object]]:
    return [
        {
            "start_session_time_us": 0,
            "end_session_time_us": 6_000_000,
            "track_id": "T1",
            "reference_target_id": "R1",
            "reported_classification": "F",
            "reference_classification": "FRIEND",
            "association_resolved": True,
            "reference_quality_status": "VALID",
        },
        {
            "start_session_time_us": 6_000_000,
            "end_session_time_us": 8_000_000,
            "track_id": "T1",
            "reference_target_id": "R1",
            "reported_classification": "HOSTILE",
            "reference_classification": "FRIEND",
            "association_resolved": True,
            "reference_quality_status": "VALID",
        },
        {
            "start_session_time_us": 8_000_000,
            "end_session_time_us": 10_000_000,
            "track_id": "T1",
            "reference_target_id": "R1",
            "reported_classification": "UNKNOWN",
            "reference_classification": "FRIEND",
            "association_resolved": True,
            "reference_quality_status": "VALID",
        },
    ]


def _golden_inputs(products: list[str]) -> dict[str, dict[str, object]]:
    taxonomy = _taxonomy_fields()
    return {
        "P1-ID-001": {
            "product_semantics": products,
            "association_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 8_000_000,
                    "track_id": "T1",
                    "reference_target_id": "R1",
                    "association_state": "CORRECT",
                },
                {
                    "start_session_time_us": 8_000_000,
                    "end_session_time_us": 10_000_000,
                    "track_id": "T1",
                    "reference_target_id": "R2",
                    "association_state": "WRONG",
                },
            ],
        },
        "P1-ID-002": {
            "product_semantics": products,
            "association_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 2_000_000,
                    "track_id": "T1",
                    "reference_target_id": "R2",
                    "association_state": "WRONG",
                },
                {
                    "start_session_time_us": 2_000_000,
                    "end_session_time_us": 3_000_000,
                    "track_id": "T1",
                    "reference_target_id": "R1",
                    "association_state": "CORRECT",
                },
                {
                    "start_session_time_us": 3_000_000,
                    "end_session_time_us": 5_000_000,
                    "track_id": "T1",
                    "reference_target_id": "R2",
                    "association_state": "WRONG",
                },
            ],
        },
        "P1-ID-003": {
            "product_semantics": products,
            "profile": {"swap_persistence_s": 2.0},
            "association_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 1_000_000,
                    "track_id": "A",
                    "reference_target_id": "R1",
                },
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 1_000_000,
                    "track_id": "B",
                    "reference_target_id": "R2",
                },
                {
                    "start_session_time_us": 1_000_000,
                    "end_session_time_us": 4_000_000,
                    "track_id": "A",
                    "reference_target_id": "R2",
                },
                {
                    "start_session_time_us": 1_000_000,
                    "end_session_time_us": 4_000_000,
                    "track_id": "B",
                    "reference_target_id": "R1",
                },
            ],
        },
        "P1-ID-004": {
            "product_semantics": products,
            "profile": {"split_persistence_s": 2.0},
            "association_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 5_000_000,
                    "track_id": "A",
                    "reference_target_id": "R1",
                },
                {
                    "start_session_time_us": 1_000_000,
                    "end_session_time_us": 4_000_000,
                    "track_id": "B",
                    "reference_target_id": "R1",
                },
            ],
        },
        "P1-ID-005": {
            "product_semantics": products,
            "profile": {"merge_persistence_s": 2.0},
            "association_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 5_000_000,
                    "track_id": "A",
                    "reference_target_id": "R1",
                },
                {
                    "start_session_time_us": 1_000_000,
                    "end_session_time_us": 4_000_000,
                    "track_id": "A",
                    "reference_target_id": "R2",
                },
            ],
        },
        "P1-ID-006": {
            "product_semantics": products,
            "profile": {"duplicate_persistence_s": 2.0},
            "association_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 10_000_000,
                    "track_id": "A",
                    "reference_target_id": "R1",
                },
                {
                    "start_session_time_us": 2_000_000,
                    "end_session_time_us": 6_000_000,
                    "track_id": "B",
                    "reference_target_id": "R1",
                },
            ],
        },
        "P1-ID-007": {
            "product_semantics": products,
            "profile": {"identity_persistence_s": 2.0, "max_gap_us": 0},
            "association_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 6_000_000,
                    "track_id": "A",
                    "reference_target_id": "R1",
                },
                {
                    "start_session_time_us": 6_000_000,
                    "end_session_time_us": 10_000_000,
                    "track_id": "B",
                    "reference_target_id": "R1",
                },
            ],
        },
        "P1-ID-008": {
            "product_semantics": products,
            **taxonomy,
            "classification_intervals": _class_intervals(),
        },
        "P1-ID-009": {
            "product_semantics": products,
            **taxonomy,
            "classification_intervals": _class_intervals(),
        },
        "P1-ID-010": {
            "product_semantics": products,
            "reported_classification_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 6_000_000,
                    "reported_classification": "FRIEND",
                    "association_resolved": True,
                },
                {
                    "start_session_time_us": 6_000_000,
                    "end_session_time_us": 8_000_000,
                    "reported_classification": "HOSTILE",
                    "association_resolved": True,
                },
                {
                    "start_session_time_us": 8_000_000,
                    "end_session_time_us": 10_000_000,
                    "reported_classification": "UNKNOWN",
                    "association_resolved": True,
                },
            ],
        },
        "P1-ID-011": {
            "product_semantics": products,
            **taxonomy,
            "stable_track_start_time_us": 1_000_000,
            "first_stable_non_unknown_correct_id_time_us": 3_500_000,
            "profile": {
                "stable_track_persistence_s": 1.0,
                "id_stability_persistence_s": 1.0,
                "max_gap_us": 100_000,
            },
        },
        "P1-ID-012": {
            "product_semantics": products,
            **taxonomy,
            "profile": {"id_stability_persistence_s": 1.0, "max_gap_us": 0},
            "classification_intervals": [
                {
                    "start_session_time_us": 0,
                    "end_session_time_us": 2_000_000,
                    "track_id": "T1",
                    "reference_target_id": "R1",
                    "reported_classification": "F",
                    "reference_classification": "FRIEND",
                    "association_resolved": True,
                    "reference_quality_status": "VALID",
                },
                {
                    "start_session_time_us": 2_000_000,
                    "end_session_time_us": 4_000_000,
                    "track_id": "T1",
                    "reference_target_id": "R1",
                    "reported_classification": "HOSTILE",
                    "reference_classification": "FRIEND",
                    "association_resolved": True,
                    "reference_quality_status": "VALID",
                },
                {
                    "start_session_time_us": 4_000_000,
                    "end_session_time_us": 6_000_000,
                    "track_id": "T1",
                    "reference_target_id": "R1",
                    "reported_classification": "FRIEND",
                    "reference_classification": "FRIEND",
                    "association_resolved": True,
                    "reference_quality_status": "VALID",
                },
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
    from tpaa_metric.m3_identification import M3_ID_CODES

    outputs: dict[str, dict[str, object]] = {}
    for code in M3_ID_CODES:
        definition = plan.definition(code)
        _plugin_id, plugin = registry.resolve(
            definition.algorithm_id,
            definition.algorithm_version,
        )
        request = M2MetricPluginRequest(
            definition=definition,
            input_payload=inputs[code],
            upstream_result_hashes=(),
            operators={},
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
    from tpaa_metric.m3_identification import (
        M3_ID_CODES,
        M3_ID_REQUIRED_PRODUCT_SEMANTICS,
        register_m3_identification_plugins,
    )
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
    positive_subject = subjects[ID_SUBJECT_ID]
    negative_subject = subjects[NEGATIVE_SUBJECT_ID]
    positive_applicability = project_m3_family_applicability(
        world_inputs,
        family_code="P1-ID-*",
        mission_system_instance_id=ID_SUBJECT_ID,
    )
    negative_applicability = project_m3_family_applicability(
        world_inputs,
        family_code="P1-ID-*",
        mission_system_instance_id=NEGATIVE_SUBJECT_ID,
    )

    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    definitions = tuple(
        sorted(
            (
                definition
                for definition in plan.definitions
                if definition.metric_code in M3_ID_CODES
            ),
            key=lambda definition: definition.metric_code,
        )
    )
    registry = MetricPluginRegistry()
    register_m3_identification_plugins(plan, registry)

    positive_inputs = _golden_inputs(list(positive_subject.product_semantics))
    engine = CatalogMetricEngine(
        plan,
        registry,
        operator_implementations=M3_AIR_OPERATOR_IMPLEMENTATIONS,
    )
    first = engine.execute(positive_inputs, metric_codes=M3_ID_CODES)
    replay = engine.execute(positive_inputs, metric_codes=M3_ID_CODES)

    direct = _direct_outputs(plan, registry, positive_inputs)
    direct_replay = _direct_outputs(plan, registry, positive_inputs)

    negative_inputs: dict[str, dict[str, object]] = {
        code: {"product_semantics": list(negative_subject.product_semantics)}
        for code in M3_ID_CODES
    }
    negative_batch = engine.execute(
        negative_inputs,
        metric_codes=M3_ID_CODES,
    )
    negative_direct = _direct_outputs(plan, registry, negative_inputs)

    id_records = tuple(
        record for record in first.records if record.metric_code in M3_ID_CODES
    )
    negative_id_records = tuple(
        record for record in negative_batch.records if record.metric_code in M3_ID_CODES
    )
    golden_numeric = {
        code: _instance(direct[code]).get("value_numeric")
        for code in M3_ID_CODES
    }
    negative_outputs_exact = all(
        output.get("applicable") is False and output.get("instances") == []
        for output in negative_direct.values()
    )

    taxonomy_negative = _golden_inputs(list(positive_subject.product_semantics))[
        "P1-ID-008"
    ]
    taxonomy_negative["reference_classification_taxonomy_hash"] = "b" * 64
    taxonomy_failed_closed = False
    try:
        _direct_outputs(
            plan,
            registry,
            {
                **positive_inputs,
                "P1-ID-008": taxonomy_negative,
            },
        )
    except ValueError as exc:
        taxonomy_failed_closed = "M3_ID_TAXONOMY_IDENTITY_MISMATCH" in str(exc)

    acceptance = {
        "identification_remainder_exact_12": (
            tuple(item.metric_code for item in definitions) == M3_ID_CODES
        ),
        "identification_family_exact": (
            {item.family for item in definitions}
            == {"ASSOCIATION_IDENTIFICATION"}
        ),
        "product_applicability_contract_exact": all(
            item.applicability.applicability_mode == "PRODUCT_CAPABILITY"
            and item.applicability.required_product_semantics
            == M3_ID_REQUIRED_PRODUCT_SEMANTICS
            for item in definitions
        ),
        "no_new_operator_binding": all(
            item.operator_bindings == () for item in definitions
        ),
        "world_positive_association_identification_product": (
            positive_applicability.applicable
            and positive_applicability.product_input_emitted
            and M3_ID_REQUIRED_PRODUCT_SEMANTICS
            in positive_subject.product_semantics
        ),
        "world_negative_product_fails_closed": (
            not negative_applicability.applicable
            and not negative_applicability.product_input_emitted
            and M3_ID_REQUIRED_PRODUCT_SEMANTICS
            not in negative_subject.product_semantics
        ),
        "single_catalog_engine_dispatch": (
            len(id_records) == 12
            and {record.plugin_id for record in id_records}
            == {
                f"m3-identification-remainder:{code}:v1"
                for code in M3_ID_CODES
            }
        ),
        "applicable_execution_exact_12": (
            {record.metric_code for record in id_records} == set(M3_ID_CODES)
            and all(
                _instance(output)["status"] == "VALID"
                for output in direct.values()
            )
        ),
        "non_applicable_execution_exact_12": (
            len(negative_id_records) == 12 and negative_outputs_exact
        ),
        "runtime_contract_product_mode_enforced": negative_outputs_exact,
        "execution_replay_exact": first == replay,
        "plugin_replay_exact": direct == direct_replay,
        "taxonomy_identity_mismatch_fails_closed": taxonomy_failed_closed,
        "golden_association_accuracy_0_8": golden_numeric["P1-ID-001"] == 0.8,
        "golden_wrong_association_count_2": golden_numeric["P1-ID-002"] == 2.0,
        "golden_track_swap_count_1": golden_numeric["P1-ID-003"] == 1.0,
        "golden_track_split_count_1": golden_numeric["P1-ID-004"] == 1.0,
        "golden_track_merge_count_1": golden_numeric["P1-ID-005"] == 1.0,
        "golden_duplicate_track_ratio_0_4": golden_numeric["P1-ID-006"] == 0.4,
        "golden_identity_continuity_0_6": golden_numeric["P1-ID-007"] == 0.6,
        "golden_identification_accuracy_0_75": golden_numeric["P1-ID-008"] == 0.75,
        "golden_false_identification_rate_0_25": (
            golden_numeric["P1-ID-009"] == 0.25
        ),
        "golden_unknown_dwell_ratio_0_2": golden_numeric["P1-ID-010"] == 0.2,
        "golden_identification_latency_2_5s": golden_numeric["P1-ID-011"] == 2.5,
        "golden_identification_stability_0_4": golden_numeric["P1-ID-012"] == 0.4,
    }
    failed = sorted(key for key, passed in acceptance.items() if not bool(passed))
    logical_product = {
        "metric_codes": list(M3_ID_CODES),
        "required_product_semantics": M3_ID_REQUIRED_PRODUCT_SEMANTICS,
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
            [record.metric_code, record.logical_hash] for record in id_records
        ],
        "negative_record_hashes": [
            [record.metric_code, record.logical_hash]
            for record in negative_id_records
        ],
        "execution_logical_hash": first.logical_hash,
        "negative_execution_logical_hash": negative_batch.logical_hash,
    }
    return {
        "schema": "TPAA_M3_MET_004_IDENTIFICATION_REMAINDER_EVIDENCE_V1",
        "task_id": "M3-MET-004",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": _git_revision(),
        "task_complete": not failed,
        "implementation_complete": not failed,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "exact_identification_remainder_12": True,
            "shared_catalog_engine": True,
            "association_identification_product_only": True,
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
        "logical_product_equal": windows.get("logical_product")
        == linux.get("logical_product"),
        "acceptance_equal": windows.get("acceptance") == linux.get("acceptance"),
        "failed_acceptance_empty": (
            windows.get("failed_acceptance") == []
            and linux.get("failed_acceptance") == []
        ),
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    return {
        "schema": "TPAA_M3_MET_004_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": "M3-MET-004",
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
            "schema": "TPAA_M3_MET_004_IDENTIFICATION_REMAINDER_EVIDENCE_V1",
            "task_id": "M3-MET-004",
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
