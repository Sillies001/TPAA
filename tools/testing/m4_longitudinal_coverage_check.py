#!/usr/bin/env python3
"""M4-TST-004 exact 104/12 longitudinal coverage qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tpaa_longitudinal import (  # noqa: E402
    M4LongitudinalError,
    M4SourceObservation,
    build_longitudinal_sample,
    build_longitudinal_scope,
    build_m4_longitudinal_eligibility,
    build_performance_trend_series,
    load_m4_longitudinal_authority,
    load_m4_trend_authority,
)
from tpaa_metric import M2MetricDefinition, build_m3_metric_execution_plan  # noqa: E402

BASELINE = ROOT / "baseline" / "CB-1.4.0"
AUTHORITY_ROOT = BASELINE / "canonical"
TRACKING_ISSUE = 129
TASK_ID = "M4-TST-004"
SESSION_ORDER_SCOPE_ID = "81000000-0000-4000-8000-000000000001"


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
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    value = completed.stdout.strip()
    return value if len(value) == 40 else "UNKNOWN"


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _id(kind: str, metric_code: str, ordinal: int = 0) -> str:
    return str(uuid5(NAMESPACE_URL, f"tpaa-m4-tst-004:{kind}:{metric_code}:{ordinal}"))


def _context() -> dict[str, object]:
    return {
        "scenario_id": "81000000-0000-4000-8000-000000000101",
        "scenario_version": "SCENARIO-V1",
        "syllabus_id": "SYLLABUS-M4",
        "syllabus_version": "1.0",
        "training_type_set": ["BASIC_FLIGHT", "BVR", "WVR"],
        "location_or_range_id": "RANGE-M4",
        "unit_id": "81000000-0000-4000-8000-000000000102",
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


def _release(
    definition: M2MetricDefinition,
    *,
    ordinal: int,
    plan: Any,
    definitions: dict[str, M2MetricDefinition],
    executions: tuple[_Execution, ...],
) -> _Release:
    return _Release(
        release_id=_id("session-release", definition.metric_code, ordinal),
        session_id=_id("session", definition.metric_code, ordinal),
        catalog_version=plan.catalog_version,
        catalog_hash=plan.catalog_sha256,
        status="PUBLISHED",
        definitions=definitions,
        execution_records=executions,
    )


def _observation(
    definition: M2MetricDefinition,
    release: _Release,
    *,
    ordinal: int,
    subject_id: str,
    configuration_key: str,
) -> M4SourceObservation:
    observation_type = (
        "CAPABILITY_OBSERVATION"
        if definition.subject_type == "AIRCRAFT"
        else "SYSTEM_PERFORMANCE_OBSERVATION"
    )
    return M4SourceObservation(
        observation_type=observation_type,
        observation_id=_id("observation", definition.metric_code, ordinal),
        release_id=release.release_id,
        session_id=release.session_id,
        metric_code=definition.metric_code,
        subject_type=definition.subject_type,
        subject_id=subject_id,
        configuration_key=configuration_key,
        episode_id=_id("episode", definition.metric_code, ordinal),
        eligibility="ELIGIBLE",
        status="VALID",
        value_numeric=100.0 + float(ordinal),
        reason_codes=(),
        coverage=1.0,
        confidence=1.0,
    )


def _error_code(action: Any) -> str:
    try:
        action()
    except M4LongitudinalError as exc:
        return exc.code
    return "NO_ERROR"


def verify() -> dict[str, object]:
    authority = load_m4_longitudinal_authority(BASELINE)
    trend_authority = load_m4_trend_authority(BASELINE)
    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    eligibility = build_m4_longitudinal_eligibility(authority, plan)
    definitions = {item.metric_code: item for item in plan.definitions}
    executions = tuple(
        _Execution(
            metric_code=item.metric_code,
            algorithm_version=item.algorithm_version,
            definition_hash=item.definition_hash,
            plugin_id=f"tpaa_metric:{item.metric_code}",
        )
        for item in plan.definitions
    )

    executed: list[dict[str, object]] = []
    for definition in eligibility.eligible:
        subject_id = _id("subject", definition.metric_code)
        configuration_key = (
            "AIRCRAFT_CONFIG_SHA256:"
            if definition.subject_type == "AIRCRAFT"
            else "MISSION_SYSTEM_CONFIG_SHA256:"
        ) + _hash({"metric_code": definition.metric_code, "configuration": "M4-TST-004"})
        metric_definition_id = _id("metric-definition", definition.metric_code)
        samples = []
        for ordinal in (1, 2, 3):
            release = _release(
                definition,
                ordinal=ordinal,
                plan=plan,
                definitions=definitions,
                executions=executions,
            )
            sample = build_longitudinal_sample(
                authority=authority,
                eligibility=eligibility,
                release=release,
                sample_id=_id("sample", definition.metric_code, ordinal),
                metric_definition_id=metric_definition_id,
                metric_code=definition.metric_code,
                subject_type=definition.subject_type,
                subject_id=subject_id,
                configuration_key=configuration_key,
                comparison_context=_context(),
                observations=(
                    _observation(
                        definition,
                        release,
                        ordinal=ordinal,
                        subject_id=subject_id,
                        configuration_key=configuration_key,
                    ),
                ),
                session_order_scope_id=SESSION_ORDER_SCOPE_ID,
                session_order=ordinal * 10,
            )
            samples.append(sample)

        scope = build_longitudinal_scope(
            authority=authority,
            sample=samples[0],
            session_order_scope_id=SESSION_ORDER_SCOPE_ID,
        )
        series = build_performance_trend_series(
            authority=trend_authority,
            release_id=_id("longitudinal-release", definition.metric_code),
            longitudinal_scope_id=_id("longitudinal-scope", definition.metric_code),
            metric_definition_id=metric_definition_id,
            metric_code=definition.metric_code,
            metric_unit="metric_unit",
            scope=scope,
            samples=tuple(samples),
            created_at_utc="2026-09-28T12:00:00Z",
        )
        executed.append(
            {
                "metric_code": definition.metric_code,
                "subject_type": definition.subject_type,
                "observation_lane": definition.observation_lane,
                "value_kind": definition.value_kind,
                "default_aggregation": definition.default_aggregation,
                "sample_count_total": series.sample_count_total,
                "sample_count_valid": series.sample_count_valid,
                "series_status": series.status,
                "trend_status": series.trend_status,
                "comparison_key_hash": series.comparison_key_hash,
                "longitudinal_scope_key": series.longitudinal_scope_key,
                "input_hash": series.input_hash,
            }
        )

    excluded_results: list[dict[str, object]] = []
    for definition in eligibility.excluded:
        release = _release(
            definition,
            ordinal=1,
            plan=plan,
            definitions=definitions,
            executions=executions,
        )
        subject_id = _id("excluded-subject", definition.metric_code)
        configuration_key = "AIRCRAFT_CONFIG_SHA256:" + "0" * 64
        expected = (
            "FAIL_CLOSED_LONGITUDINAL_SUBJECT_FORBIDDEN"
            if definition.subject_type not in authority.admitted_subject_types
            else "FAIL_CLOSED_NOT_LONGITUDINAL_ELIGIBLE"
        )
        actual = _error_code(
            lambda definition=definition, release=release, subject_id=subject_id, configuration_key=configuration_key: (
                build_longitudinal_sample(
                    authority=authority,
                    eligibility=eligibility,
                    release=release,
                    sample_id=_id("excluded-sample", definition.metric_code),
                    metric_definition_id=_id(
                        "excluded-definition",
                        definition.metric_code,
                    ),
                    metric_code=definition.metric_code,
                    subject_type=definition.subject_type,
                    subject_id=subject_id,
                    configuration_key=configuration_key,
                    comparison_context=_context(),
                    observations=(),
                    session_order_scope_id=SESSION_ORDER_SCOPE_ID,
                    session_order=10,
                )
            )
        )
        excluded_results.append(
            {
                "metric_code": definition.metric_code,
                "subject_type": definition.subject_type,
                "observation_lane": definition.observation_lane,
                "value_kind": definition.value_kind,
                "default_aggregation": definition.default_aggregation,
                "expected_error": expected,
                "actual_error": actual,
                "sample_created": False,
                "trend_created": False,
            }
        )

    eligible_codes = tuple(item["metric_code"] for item in executed)
    excluded_codes = tuple(item["metric_code"] for item in excluded_results)
    expected_eligible = tuple(
        item.metric_code
        for item in plan.definitions
        if item.p1_longitudinal_trend_eligibility
    )
    expected_excluded = tuple(
        item.metric_code
        for item in plan.definitions
        if not item.p1_longitudinal_trend_eligibility
    )
    acceptance = {
        "catalog_exact_116": len(plan.definitions) == 116,
        "eligible_exact_104": (
            len(executed) == 104
            and len(set(eligible_codes)) == 104
            and eligible_codes == expected_eligible
        ),
        "excluded_exact_12": (
            len(excluded_results) == 12
            and len(set(excluded_codes)) == 12
            and excluded_codes == expected_excluded
        ),
        "all_104_execute_sample_and_trend": all(
            row["sample_count_total"] == 3
            and row["sample_count_valid"] == 3
            and row["series_status"] == "VALID"
            for row in executed
        ),
        "eligible_membership_contract_exact": all(
            row["subject_type"] in authority.admitted_subject_types
            and row["observation_lane"] != "QUALITY_EVIDENCE_ONLY"
            and row["value_kind"] == "NUMERIC"
            and row["default_aggregation"] == "MEDIAN"
            for row in executed
        ),
        "all_12_excluded_fail_closed": all(
            row["actual_error"] == row["expected_error"]
            and row["sample_created"] is False
            and row["trend_created"] is False
            for row in excluded_results
        ),
        "eligible_excluded_partition_exact": (
            set(eligible_codes).isdisjoint(excluded_codes)
            and set(eligible_codes) | set(excluded_codes)
            == {item.metric_code for item in plan.definitions}
        ),
        "p4_p5_inactive": authority.p4_p5_human_team_assessment_active is False,
        "m5_qualification_not_claimed": (
            authority.m5_formal_product_qualification_claimed is False
        ),
    }
    failed = sorted(name for name, value in acceptance.items() if value is not True)
    logical_product = {
        "catalog_version": plan.catalog_version,
        "catalog_hash": plan.catalog_sha256,
        "eligible": executed,
        "excluded": excluded_results,
    }
    return {
        "schema": "TPAA_M4_TST_004_LONGITUDINAL_COVERAGE_V1",
        "task_id": TASK_ID,
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "implementation_complete": not failed,
        "task_complete": False,
        "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
        "source_revision": _git_revision(),
        "logical_product": logical_product,
        "logical_product_hash": _hash(logical_product),
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "p1_only": True,
            "eligible_metric_count": 104,
            "excluded_metric_count": 12,
            "db_schema_version": "1.6.0",
            "shadow_schema_created": False,
            "p4_p5_human_team_assessment_active": False,
            "m5_formal_product_qualification_claimed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = verify()
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M4_TST_004_LONGITUDINAL_COVERAGE_V1",
            "task_id": TASK_ID,
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
