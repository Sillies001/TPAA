#!/usr/bin/env python3
"""M4 Batch 1 executable evidence for longitudinal sample substrate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = str(REPO_ROOT / "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from tpaa_longitudinal import (  # noqa: E402
    M4LongitudinalError,
    M4SourceObservation,
    build_comparison_key,
    build_longitudinal_sample,
    build_longitudinal_scope,
    build_m4_longitudinal_eligibility,
    load_m4_longitudinal_authority,
    validate_m4_product_scope,
)
from tpaa_metric import M2MetricDefinition, build_m3_metric_execution_plan  # noqa: E402

BASELINE = REPO_ROOT / "baseline" / "CB-1.4.0"
AUTHORITY_ROOT = BASELINE / "canonical"
TRACKING_ISSUE = 126

RELEASE_ID = "20000000-0000-4000-8000-000000000001"
SESSION_ID = "20000000-0000-4000-8000-000000000002"
SUBJECT_ID = "20000000-0000-4000-8000-000000000003"
METRIC_DEFINITION_ID = "20000000-0000-4000-8000-000000000004"
SAMPLE_ID = "20000000-0000-4000-8000-000000000005"
SESSION_ORDER_SCOPE_ID = "20000000-0000-4000-8000-000000000006"
CONFIGURATION_KEY = "MISSION_SYSTEM_CONFIG_SHA256:" + "a" * 64


@dataclass(frozen=True)
class _Execution:
    metric_code: str
    algorithm_version: str
    definition_hash: str
    plugin_id: str


@dataclass(frozen=True)
class _Release:
    release_id: str
    session_id: str
    catalog_version: str
    catalog_hash: str
    status: str
    definitions: dict[str, M2MetricDefinition]
    execution_records: tuple[_Execution, ...]

    def definition(self, metric_code: str) -> M2MetricDefinition:
        return self.definitions[metric_code]


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


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _context() -> dict[str, object]:
    return {
        "scenario_id": "20000000-0000-4000-8000-000000000101",
        "scenario_version": "SCENARIO-V1",
        "syllabus_id": "SYLLABUS-A",
        "syllabus_version": "1.0",
        "training_type_set": ["BASIC_FLIGHT", "BVR", "WVR"],
        "location_or_range_id": "RANGE-A",
        "unit_id": "20000000-0000-4000-8000-000000000102",
        "role_model_version": "ROLE-V1",
        "context_version": "CTX-V1",
        "rule_set_version": "RULE-V1",
        "reference_set_version": "REF-V1",
        "metric_profile_version": "METRIC-PROFILE-V1",
        "world_product_versions": {
            "FLIGHT_KINEMATICS": "1.0.0",
            "MISSION_CONTEXT": "1.0.0",
        },
    }


def _observations(metric_code: str) -> tuple[M4SourceObservation, ...]:
    raw: tuple[tuple[str, float | None, str, float, float], ...] = (
        ("20000000-0000-4000-8000-000000001001", 8.0, "VALID", 0.95, 0.90),
        (
            "20000000-0000-4000-8000-000000001002",
            None,
            "INSUFFICIENT_DATA",
            0.50,
            0.40,
        ),
        ("20000000-0000-4000-8000-000000001003", 2.0, "VALID", 0.80, 0.70),
        ("20000000-0000-4000-8000-000000001004", 5.0, "VALID", 1.00, 0.85),
    )
    return tuple(
        M4SourceObservation(
            observation_type="SYSTEM_PERFORMANCE_OBSERVATION",
            observation_id=observation_id,
            release_id=RELEASE_ID,
            session_id=SESSION_ID,
            metric_code=metric_code,
            subject_type="MISSION_SYSTEM_INSTANCE",
            subject_id=SUBJECT_ID,
            configuration_key=CONFIGURATION_KEY,
            episode_id=f"20000000-0000-4000-8000-{index + 1:012d}",
            eligibility="ELIGIBLE",
            status=status,
            value_numeric=value,
            reason_codes=("SOURCE_GAP",) if status != "VALID" else (),
            coverage=coverage,
            confidence=confidence,
        )
        for index, (observation_id, value, status, coverage, confidence) in enumerate(raw)
    )


def _error_code(action: Any) -> str:
    try:
        action()
    except M4LongitudinalError as exc:
        return exc.code
    return "NO_ERROR"


def verify() -> dict[str, object]:
    authority = load_m4_longitudinal_authority(BASELINE)
    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    eligibility = build_m4_longitudinal_eligibility(authority, plan)
    definition = next(
        item
        for item in eligibility.eligible
        if item.subject_type == "MISSION_SYSTEM_INSTANCE"
    )
    release = _Release(
        release_id=RELEASE_ID,
        session_id=SESSION_ID,
        catalog_version=plan.catalog_version,
        catalog_hash=plan.catalog_sha256,
        status="PUBLISHED",
        definitions={item.metric_code: item for item in plan.definitions},
        execution_records=tuple(
            _Execution(
                metric_code=item.metric_code,
                algorithm_version=item.algorithm_version,
                definition_hash=item.definition_hash,
                plugin_id=f"tpaa_metric:{item.metric_code}",
            )
            for item in plan.definitions
        ),
    )
    observations = _observations(definition.metric_code)
    sample = build_longitudinal_sample(
        authority=authority,
        eligibility=eligibility,
        release=release,
        sample_id=SAMPLE_ID,
        metric_definition_id=METRIC_DEFINITION_ID,
        metric_code=definition.metric_code,
        subject_type="MISSION_SYSTEM_INSTANCE",
        subject_id=SUBJECT_ID,
        configuration_key=CONFIGURATION_KEY,
        comparison_context=_context(),
        observations=observations,
        session_order_scope_id=SESSION_ORDER_SCOPE_ID,
        session_order=10,
    )
    replay = build_longitudinal_sample(
        authority=authority,
        eligibility=eligibility,
        release=release,
        sample_id=SAMPLE_ID,
        metric_definition_id=METRIC_DEFINITION_ID,
        metric_code=definition.metric_code,
        subject_type="MISSION_SYSTEM_INSTANCE",
        subject_id=SUBJECT_ID,
        configuration_key=CONFIGURATION_KEY,
        comparison_context=dict(reversed(tuple(_context().items()))),
        observations=tuple(reversed(observations)),
        session_order_scope_id=SESSION_ORDER_SCOPE_ID,
        session_order=10,
    )
    no_valid_observations = (
        replace(
            observations[0],
            status="N_A",
            value_numeric=None,
            reason_codes=("NO_APPLICABLE_WINDOW",),
        ),
        replace(
            observations[1],
            status="INSUFFICIENT_DATA",
            value_numeric=None,
            reason_codes=("SOURCE_GAP",),
        ),
    )
    no_valid_sample = build_longitudinal_sample(
        authority=authority,
        eligibility=eligibility,
        release=release,
        sample_id="20000000-0000-4000-8000-000000000007",
        metric_definition_id=METRIC_DEFINITION_ID,
        metric_code=definition.metric_code,
        subject_type="MISSION_SYSTEM_INSTANCE",
        subject_id=SUBJECT_ID,
        configuration_key=CONFIGURATION_KEY,
        comparison_context=_context(),
        observations=no_valid_observations,
        session_order_scope_id=SESSION_ORDER_SCOPE_ID,
        session_order=10,
    )
    scope = build_longitudinal_scope(
        authority=authority,
        sample=sample,
        session_order_scope_id=SESSION_ORDER_SCOPE_ID,
    )
    changed_context = _context()
    changed_context["scenario_version"] = "SCENARIO-V2"
    changed = build_longitudinal_sample(
        authority=authority,
        eligibility=eligibility,
        release=release,
        sample_id=SAMPLE_ID,
        metric_definition_id=METRIC_DEFINITION_ID,
        metric_code=definition.metric_code,
        subject_type="MISSION_SYSTEM_INSTANCE",
        subject_id=SUBJECT_ID,
        configuration_key=CONFIGURATION_KEY,
        comparison_context=changed_context,
        observations=observations,
        session_order_scope_id=SESSION_ORDER_SCOPE_ID,
        session_order=10,
    )
    changed_scope = build_longitudinal_scope(
        authority=authority,
        sample=changed,
        session_order_scope_id=SESSION_ORDER_SCOPE_ID,
    )

    authority_payload = json.loads(
        (AUTHORITY_ROOT / "M4_LONGITUDINAL_DEBRIEF_AUTHORITY.json").read_text(
            encoding="utf-8"
        )
    )
    comparison_golden = authority_payload["golden_vectors"]["comparison_key"]
    _golden_key, golden_hash = build_comparison_key(
        authority,
        comparison_golden["permutation_input"],
    )

    excluded_code = eligibility.excluded[0].metric_code
    excluded_error = _error_code(
        lambda: build_longitudinal_sample(
            authority=authority,
            eligibility=eligibility,
            release=release,
            sample_id=SAMPLE_ID,
            metric_definition_id=METRIC_DEFINITION_ID,
            metric_code=excluded_code,
            subject_type=eligibility.excluded[0].subject_type,
            subject_id=SUBJECT_ID,
            configuration_key=CONFIGURATION_KEY,
            comparison_context=_context(),
            observations=(),
        )
    )
    not_applicable_error = _error_code(
        lambda: build_longitudinal_sample(
            authority=authority,
            eligibility=eligibility,
            release=release,
            sample_id=SAMPLE_ID,
            metric_definition_id=METRIC_DEFINITION_ID,
            metric_code=definition.metric_code,
            subject_type="MISSION_SYSTEM_INSTANCE",
            subject_id=SUBJECT_ID,
            configuration_key=CONFIGURATION_KEY,
            comparison_context=_context(),
            observations=(replace(observations[0], eligibility="NOT_APPLICABLE"),),
        )
    )
    p4_error = _error_code(
        lambda: validate_m4_product_scope(
            authority,
            capability_phase="P4",
            subject_type="AIRCRAFT",
            claims_m5_formal_product_qualification=False,
        )
    )
    m5_error = _error_code(
        lambda: validate_m4_product_scope(
            authority,
            capability_phase="P1",
            subject_type="AIRCRAFT",
            claims_m5_formal_product_qualification=True,
        )
    )

    acceptance = {
        "authority_controlled_and_loadable": authority.version == "1.0.0",
        "gov_p1_only_guard": p4_error == "M4_GOV_P1_ONLY",
        "gov_p4_p5_inactive": authority.p4_p5_human_team_assessment_active is False,
        "gov_m5_claim_guard": m5_error == "M4_GOV_M5_QUALIFICATION_CLAIM_FORBIDDEN",
        "catalog_exact_116": len(plan.definitions) == 116,
        "longitudinal_eligible_exact_104": len(eligibility.eligible_codes) == 104,
        "longitudinal_excluded_exact_12": len(eligibility.excluded_codes) == 12,
        "eligible_numeric_median_exact": all(
            item.value_kind == "NUMERIC" and item.default_aggregation == "MEDIAN"
            for item in eligibility.eligible
        ),
        "eligible_subjects_exact": all(
            item.subject_type in {"AIRCRAFT", "MISSION_SYSTEM_INSTANCE"}
            for item in eligibility.eligible
        ),
        "quality_only_excluded": all(
            item.observation_lane != "QUALITY_EVIDENCE_ONLY"
            for item in eligibility.eligible
        ),
        "sample_median_exact": sample.value_numeric == 5.0,
        "sample_status_exact": sample.status == "VALID" and sample.reason_codes == (),
        "sample_quality_exact": sample.coverage == 0.80 and sample.confidence == 0.70,
        "sample_episode_count_exact": sample.source_episode_count == 3,
        "sample_release_lineage_exact": (
            sample.release_id == RELEASE_ID
            and sample.session_id == SESSION_ID
            and all(ref[2] == RELEASE_ID for ref in sample.source_observation_refs)
        ),
        "sample_replay_exact": sample == replay,
        "nonvalid_sample_does_not_fabricate_numeric_value": (
            no_valid_sample.value_numeric is None
            and no_valid_sample.status == "INSUFFICIENT_DATA"
            and no_valid_sample.source_episode_count == 0
            and "M4_LONGITUDINAL_NO_VALID_VALUE" in no_valid_sample.reason_codes
        ),
        "excluded_metric_fails_closed": (
            excluded_error == "FAIL_CLOSED_NOT_LONGITUDINAL_ELIGIBLE"
        ),
        "not_applicable_source_fails_closed": (
            not_applicable_error == "M4_LONGITUDINAL_SOURCE_NOT_ELIGIBLE"
        ),
        "comparison_authority_golden_exact": (
            golden_hash == comparison_golden["expected_hash"]
        ),
        "material_context_segments": (
            sample.comparison_key_hash != changed.comparison_key_hash
        ),
        "scope_identity_segments": (
            scope.longitudinal_scope_key != changed_scope.longitudinal_scope_key
        ),
        "scope_key_equals_descriptor_hash": (
            scope.longitudinal_scope_key == scope.descriptor_hash
        ),
    }
    failed = sorted(name for name, passed in acceptance.items() if not passed)
    logical_product = {
        "catalog_version": plan.catalog_version,
        "catalog_hash": plan.catalog_sha256,
        "eligible_codes": list(eligibility.eligible_codes),
        "excluded_codes": list(eligibility.excluded_codes),
        "sample": sample.projection(),
        "no_valid_sample": no_valid_sample.projection(),
        "scope": scope.projection(),
    }
    return {
        "schema": "TPAA_M4_BATCH_1_LONGITUDINAL_SAMPLE_EVIDENCE_V1",
        "tracking_issue": TRACKING_ISSUE,
        "task_ids": [
            "M4-GOV-001",
            "M4-GOV-002",
            "M4-LONG-001",
            "M4-LONG-002",
            "M4-LONG-003",
            "M4-TST-001",
        ],
        "status": "PASS" if not failed else "FAIL",
        "implementation_complete": not failed,
        "task_complete": False,
        "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
        "source_revision": _git_revision(),
        "logical_product": logical_product,
        "logical_product_hash": _canonical_hash(logical_product),
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "p1_only": True,
            "p4_p5_human_team_assessment_active": False,
            "m5_formal_product_qualification_claimed": False,
            "db_schema_version": "1.6.0",
            "shadow_schema_created": False,
            "trend_engine_executed": False,
            "api_gui_implemented": False,
            "persistence_schema_changed": False,
        },
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
            "schema": "TPAA_M4_BATCH_1_LONGITUDINAL_SAMPLE_EVIDENCE_V1",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2
    rendered = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
    print(rendered, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
