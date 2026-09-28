from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from tpaa_longitudinal import (
    M4LongitudinalError,
    M4SourceObservation,
    build_comparison_key,
    build_longitudinal_sample,
    build_longitudinal_scope,
    build_m4_longitudinal_eligibility,
    load_m4_longitudinal_authority,
    validate_m4_product_scope,
)
from tpaa_metric import M2MetricDefinition, build_m3_metric_execution_plan

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
AUTHORITY_ROOT = BASELINE / "canonical"

RELEASE_ID = "10000000-0000-4000-8000-000000000001"
SESSION_ID = "10000000-0000-4000-8000-000000000002"
SUBJECT_ID = "10000000-0000-4000-8000-000000000003"
METRIC_DEFINITION_ID = "10000000-0000-4000-8000-000000000004"
SAMPLE_ID = "10000000-0000-4000-8000-000000000005"
SESSION_ORDER_SCOPE_ID = "10000000-0000-4000-8000-000000000006"
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


def _context() -> dict[str, object]:
    return {
        "scenario_id": "10000000-0000-4000-8000-000000000101",
        "scenario_version": "SCENARIO-V1",
        "syllabus_id": "SYLLABUS-A",
        "syllabus_version": "1.0",
        "training_type_set": ["BASIC_FLIGHT", "BVR", "WVR"],
        "location_or_range_id": "RANGE-A",
        "unit_id": "10000000-0000-4000-8000-000000000102",
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


def _setup() -> tuple[object, object, _Release, M2MetricDefinition]:
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
    return authority, eligibility, release, definition


def _observations(metric_code: str) -> tuple[M4SourceObservation, ...]:
    values = (
        ("10000000-0000-4000-8000-000000001001", 8.0, "VALID", 0.95, 0.90),
        (
            "10000000-0000-4000-8000-000000001002",
            None,
            "INSUFFICIENT_DATA",
            0.50,
            0.40,
        ),
        ("10000000-0000-4000-8000-000000001003", 2.0, "VALID", 0.80, 0.70),
        ("10000000-0000-4000-8000-000000001004", 5.0, "VALID", 1.00, 0.85),
    )
    result: list[M4SourceObservation] = []
    for index, (observation_id, value, status, coverage, confidence) in enumerate(values):
        result.append(
            M4SourceObservation(
                observation_type="SYSTEM_PERFORMANCE_OBSERVATION",
                observation_id=observation_id,
                release_id=RELEASE_ID,
                session_id=SESSION_ID,
                metric_code=metric_code,
                subject_type="MISSION_SYSTEM_INSTANCE",
                subject_id=SUBJECT_ID,
                configuration_key=CONFIGURATION_KEY,
                episode_id=f"10000000-0000-4000-8000-{index + 1:012d}",
                eligibility="ELIGIBLE",
                status=status,
                value_numeric=value,
                reason_codes=("SOURCE_GAP",) if status != "VALID" else (),
                coverage=coverage,
                confidence=confidence,
            )
        )
    return tuple(result)


def _sample(
    *,
    context: dict[str, object] | None = None,
    observations: tuple[M4SourceObservation, ...] | None = None,
):
    authority, eligibility, release, definition = _setup()
    return build_longitudinal_sample(
        authority=authority,
        eligibility=eligibility,
        release=release,
        sample_id=SAMPLE_ID,
        metric_definition_id=METRIC_DEFINITION_ID,
        metric_code=definition.metric_code,
        subject_type="MISSION_SYSTEM_INSTANCE",
        subject_id=SUBJECT_ID,
        configuration_key=CONFIGURATION_KEY,
        comparison_context=context or _context(),
        observations=observations or _observations(definition.metric_code),
        session_order_scope_id=SESSION_ORDER_SCOPE_ID,
        session_order=10,
    )


def test_m4_longitudinal_catalog_projection_is_exact_104_12() -> None:
    authority, eligibility, _release, _definition = _setup()
    assert len(eligibility.eligible_codes) == 104
    assert len(eligibility.excluded_codes) == 12
    assert all(item.value_kind == "NUMERIC" for item in eligibility.eligible)
    assert all(item.default_aggregation == "MEDIAN" for item in eligibility.eligible)
    assert all(
        item.subject_type in authority.admitted_subject_types
        for item in eligibility.eligible
    )
    assert all(
        item.observation_lane != "QUALITY_EVIDENCE_ONLY"
        for item in eligibility.eligible
    )


def test_m4_comparison_key_matches_authority_golden_and_set_order_is_stable() -> None:
    authority = load_m4_longitudinal_authority(BASELINE)
    payload = json.loads(
        (AUTHORITY_ROOT / "M4_LONGITUDINAL_DEBRIEF_AUTHORITY.json").read_text(
            encoding="utf-8"
        )
    )
    golden = payload["golden_vectors"]["comparison_key"]
    _canonical, digest = build_comparison_key(
        authority,
        golden["permutation_input"],
    )
    assert digest == golden["expected_hash"]

    broken = dict(golden["canonical_input"])
    broken["training_type_set"] = ["BVR", "BVR"]
    with pytest.raises(M4LongitudinalError) as excinfo:
        build_comparison_key(authority, broken)
    assert excinfo.value.code == "FAIL_CLOSED_SET_ARRAY_DUPLICATE"


def test_m4_sample_median_release_lineage_and_replay_are_deterministic() -> None:
    sample = _sample()
    # Rebuild with reversed mapping/source order to prove deterministic replay.
    authority, eligibility, release, definition = _setup()
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
        observations=tuple(reversed(_observations(definition.metric_code))),
        session_order_scope_id=SESSION_ORDER_SCOPE_ID,
        session_order=10,
    )
    assert sample == replay
    assert sample.value_numeric == 5.0
    assert sample.status == "VALID"
    assert sample.reason_codes == ()
    assert sample.coverage == 0.80
    assert sample.confidence == 0.70
    assert sample.source_episode_count == 3
    assert sample.release_id == RELEASE_ID
    assert sample.session_id == SESSION_ID
    assert all(ref[2] == RELEASE_ID for ref in sample.source_observation_refs)
    assert len(sample.logical_content_hash) == 64


def test_m4_sample_excluded_and_not_applicable_inputs_fail_closed() -> None:
    authority, eligibility, release, definition = _setup()
    excluded = next(
        item
        for item in eligibility.excluded
        if item.subject_type in authority.admitted_subject_types
    )
    with pytest.raises(M4LongitudinalError) as excinfo:
        build_longitudinal_sample(
            authority=authority,
            eligibility=eligibility,
            release=release,
            sample_id=SAMPLE_ID,
            metric_definition_id=METRIC_DEFINITION_ID,
            metric_code=excluded.metric_code,
            subject_type=excluded.subject_type,
            subject_id=SUBJECT_ID,
            configuration_key=CONFIGURATION_KEY,
            comparison_context=_context(),
            observations=(),
        )
    assert excinfo.value.code == "FAIL_CLOSED_NOT_LONGITUDINAL_ELIGIBLE"

    observations = _observations(definition.metric_code)
    not_applicable = (replace(observations[0], eligibility="NOT_APPLICABLE"),)
    with pytest.raises(M4LongitudinalError) as excinfo:
        build_longitudinal_sample(
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
            observations=not_applicable,
        )
    assert excinfo.value.code == "M4_LONGITUDINAL_SOURCE_NOT_ELIGIBLE"


def test_m4_scope_segments_material_context_changes() -> None:
    authority = load_m4_longitudinal_authority(BASELINE)
    first = _sample()
    changed = _context()
    changed["scenario_version"] = "SCENARIO-V2"
    second = _sample(context=changed)
    assert first.comparison_key_hash != second.comparison_key_hash

    first_scope = build_longitudinal_scope(
        authority=authority,
        sample=first,
        session_order_scope_id=SESSION_ORDER_SCOPE_ID,
    )
    second_scope = build_longitudinal_scope(
        authority=authority,
        sample=second,
        session_order_scope_id=SESSION_ORDER_SCOPE_ID,
    )
    assert first_scope.longitudinal_scope_key == first_scope.descriptor_hash
    assert first_scope.longitudinal_scope_key != second_scope.longitudinal_scope_key


def test_m4_governance_guard_is_p1_only_and_pre_m5() -> None:
    authority = load_m4_longitudinal_authority(BASELINE)
    validate_m4_product_scope(
        authority,
        capability_phase="P1",
        subject_type="AIRCRAFT",
        claims_m5_formal_product_qualification=False,
    )
    with pytest.raises(M4LongitudinalError) as excinfo:
        validate_m4_product_scope(
            authority,
            capability_phase="P4",
            subject_type="AIRCRAFT",
            claims_m5_formal_product_qualification=False,
        )
    assert excinfo.value.code == "M4_GOV_P1_ONLY"
    with pytest.raises(M4LongitudinalError) as excinfo:
        validate_m4_product_scope(
            authority,
            capability_phase="P1",
            subject_type="AIRCRAFT",
            claims_m5_formal_product_qualification=True,
        )
    assert excinfo.value.code == "M4_GOV_M5_QUALIFICATION_CLAIM_FORBIDDEN"
