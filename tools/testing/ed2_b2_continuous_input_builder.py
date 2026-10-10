#!/usr/bin/env python3
"""Build the packaged ED2 B2 continuous production-chain qualification plan."""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID, uuid5

from tools.testing.ed2_p1_full_input_builder import build_full_p1_request_contract
from tpaa_runtime.production_p1_catalog import (
    build_production_p1_catalog_contract,
    execute_production_p1_catalog,
)
from tpaa_runtime.production_p1_request import (
    parse_production_p1_request,
    select_production_p1_sources,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
NOMINAL_FLIGHT = (
    REPO_ROOT
    / "docs"
    / "baseline"
    / "PRCB-1.0"
    / "qualification"
    / "PRCB_C2_NOMINAL_FLIGHT.json"
)

ED2_B2_CONTINUOUS_QUALIFICATION_SCHEMA = (
    "TPAA_ED2_B2_CONTINUOUS_QUALIFICATION_PLAN_V1"
)
_NAMESPACE = UUID("ed2b2000-0000-4000-8000-000000000001")
_AIRCRAFT_ID = str(uuid5(_NAMESPACE, "aircraft:1"))
_AIRCRAFT_MODEL_ID = str(uuid5(_NAMESPACE, "aircraft-model:1"))
_CONTEXT_VERSION = "ED2-B2-CONTEXT-1.0.0"
_RULE_SET_VERSION = "ED2-B2-RULES-1.0.0"
_METRIC_PROFILE_VERSION = "ED2_B2_P1_PROFILE_V1"


def _id(kind: str, ordinal: int) -> str:
    return str(uuid5(_NAMESPACE, f"{kind}:{ordinal}"))


def _flight_source(ordinal: int) -> str:
    raw: object = json.loads(NOMINAL_FLIGHT.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("ED2_B2_NOMINAL_FLIGHT_INVALID")
    document = dict(cast(dict[str, object], raw))
    document["session_id"] = _id("session", ordinal)
    document["aircraft_id"] = _AIRCRAFT_ID
    rows = document.get("rows")
    if not isinstance(rows, list) or not rows:
        raise TypeError("ED2_B2_NOMINAL_FLIGHT_ROWS_INVALID")
    # Preserve the flight shape while making each Session's metric outcomes
    # independently identifiable in publication hashes.
    delta = float(ordinal - 1)
    rewritten: list[object] = []
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("ED2_B2_NOMINAL_FLIGHT_ROW_INVALID")
        item = dict(cast(dict[str, object], row))
        tas = item.get("tas")
        mach = item.get("mach")
        if isinstance(tas, (int, float)) and not isinstance(tas, bool):
            item["tas"] = float(tas) + delta
        if isinstance(mach, (int, float)) and not isinstance(mach, bool):
            item["mach"] = float(mach) + delta * 0.001
        rewritten.append(item)
    document["rows"] = rewritten
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _p1_payload(ordinal: int) -> dict[str, object]:
    session_id = _id("session", ordinal)
    source_json = _flight_source(ordinal)
    contract = build_full_p1_request_contract(
        aircraft_id=_AIRCRAFT_ID,
        authority_root=AUTHORITY,
        flight_source_json=source_json,
        system_id_namespace=_NAMESPACE,
    )
    payload: dict[str, object] = {
        "source_json": source_json,
        "source_import": {
            "source_family": "FLIGHT",
            "source_id": _id("source", ordinal),
            "session_id": session_id,
            "platform_id": None,
            "producer_system": "ED2_B2_CONTINUOUS_QUALIFICATION",
            "schema_name": "TPAA_PRODUCTION_FLIGHT_SOURCE_V1",
            "schema_version": "1.0.0",
            "time_basis": "SOURCE_US",
            "nominal_rate_hz": "10.0",
            "source_quality": "1.0",
            "source_stream_id": _id("stream", ordinal),
            "stream_code": "FLIGHT_PRIMARY",
            "ordinal_basis": "SOURCE_SEQUENCE",
            "stream_status": "ACTIVE",
            "artifact_id": _id("artifact", ordinal),
            "source_artifact_sequence": 0,
            "uri_kind": "EXTERNAL_FILE",
            "availability_status": "AVAILABLE",
            "last_verified_at": "2026-10-08T00:00:00Z",
            "mtime_source": None,
            "source_ref": (
                f"qualification://ED2_B2_CONTINUOUS/session-{ordinal}"
            ),
            "media_type": "application/vnd.tpaa.flight+json",
            "classification_label": "UNCLASSIFIED",
            "session_code": f"ED2-B2-CONTINUOUS-{ordinal}",
            "session_type": "SIM",
        },
        "evaluation_context": {
            "context_id": _id("context", ordinal),
            "session_id": session_id,
            "context_version": _CONTEXT_VERSION,
            "revision_no": 1,
            "rule_set_version": _RULE_SET_VERSION,
            "metric_profile_version": _METRIC_PROFILE_VERSION,
            "status": "ACTIVE",
        },
        "publication_identity": {
            "aircraft_model_id": _AIRCRAFT_MODEL_ID,
            "aircraft_instance_id": _id("aircraft-instance", ordinal),
            "subject_entity_id": _id("subject-entity", ordinal),
            "capability_dimension": "AIRCRAFT_FLIGHT",
            "capability_type": "KINEMATIC_ENERGY_CONTROL",
            "aircraft_type_code": "ED2-B2-TYPE",
            "aircraft_model_name": "ED2 B2 Continuous Qualification Aircraft",
            "aircraft_internal_code": "ED2-B2-AIRCRAFT",
            "entity_alias": f"ED2-B2-SUBJECT-{ordinal}",
        },
        "expected_version_token": 0,
        "parent_release_id": None,
    }
    payload.update(contract)
    return payload


def verify_p2_jackknife_support(
    values_by_ordinal: Mapping[str, str],
    *,
    reference_value: str,
    historical_count: int = 4,
) -> None:
    """Qualify every historical target against each leave-one-subject-out cohort."""

    if set(values_by_ordinal) != {str(i) for i in range(1, 9)}:
        raise ValueError("ED2_B2_P2_REFERENCE_SUBJECT_COUNT_INVALID")
    values = tuple(Decimal(values_by_ordinal[str(i)]) for i in range(1, 9))
    reference = Decimal(reference_value)
    if not all(value.is_finite() for value in (*values, reference)):
        raise ValueError("ED2_B2_P2_REFERENCE_NOT_FINITE")
    for target_index in range(historical_count):
        target = values[target_index]
        cohort = [
            value for index, value in enumerate(values)
            if index != target_index
        ]
        for omitted in range(len(cohort)):
            remaining = cohort[:omitted] + cohort[omitted + 1 :]
            if (
                len(set(remaining)) < 2
                or min(remaining) > min(target, reference)
                or max(remaining) < max(target, reference)
            ):
                raise ValueError(
                    f"ED2_B2_P2_JACKKNIFE_SUPPORT_INSUFFICIENT:{target_index + 1}"
                )


def build_ed2_b2_continuous_qualification_plan() -> dict[str, object]:
    # Qualification-only preflight uses the same governed Catalog path as the
    # installed Worker, with no persistence or qualification seed substitution.
    catalog = build_production_p1_catalog_contract(AUTHORITY)
    sessions = []
    for ordinal in range(1, 9):
        payload = _p1_payload(ordinal)
        sources = select_production_p1_sources(payload)
        request = parse_production_p1_request(
            payload,
            contract=catalog,
            aircraft_id=_AIRCRAFT_ID,
            source_selection=sources,
        )
        executed, batch = execute_production_p1_catalog(AUTHORITY, request.inputs)
        if (
            executed.plan.logical_hash != catalog.plan.logical_hash
            or batch.metric_codes != catalog.metric_codes
        ):
            raise RuntimeError("ED2_B2_QUALIFICATION_P1_PREFLIGHT_DRIFT")
        sessions.append(
            {
                "ordinal": ordinal,
                "role": (
                    "P3_HISTORY"
                    if ordinal <= 4
                    else "P4_P5_EVALUATION"
                    if ordinal == 5
                    else "P2_INDEPENDENT_REFERENCE"
                ),
                "session_id": _id("session", ordinal),
                "context_id": _id("context", ordinal),
                "occurred_at_utc": (
                    f"2026-10-{ordinal:02d}T12:00:00Z"
                ),
                "p1_payload": payload,
            }
        )
    p2_factor_values = {
        "1": "0.35",
        "2": "0.45",
        "3": "0.55",
        "4": "0.65",
        "5": "0.0",
        "6": "0.1",
        "7": "0.9",
        "8": "1.0",
    }
    verify_p2_jackknife_support(
        p2_factor_values,
        reference_value="0.5",
    )
    return {
        "schema": ED2_B2_CONTINUOUS_QUALIFICATION_SCHEMA,
        "aircraft_id": _AIRCRAFT_ID,
        "aircraft_model_id": _AIRCRAFT_MODEL_ID,
        "sessions": sessions,
        "p2_profile": {
            "as_of_utc": "2029-12-31T23:30:00Z",
            "factor_order": ["SESSION_CONTEXT_FACTOR"],
            "factor_values_by_ordinal": p2_factor_values,
            "reference_factor_values": {
                "SESSION_CONTEXT_FACTOR": "0.5"
            },
            "cohort_spec_id": "ED2_B2_P2_COHORT_V1",
            "cohort_spec_version": "1.0.0",
            "feature_spec": {
                "logical_key": "P2_FACTOR_FEATURE_SPEC:ED2_B2_CONTINUOUS",
                "artifact_version": "1.0.0",
                "schema_version": "TPAA_P2_FACTOR_FEATURE_SPEC_V1",
                "payload": {
                    "schema": "TPAA_P2_FACTOR_FEATURE_SPEC_V1",
                    "factor_order": ["SESSION_CONTEXT_FACTOR"],
                    "semantics": "ED2_B2_QUALIFICATION_CONTEXT_AXIS",
                },
            },
            "reference_condition": {
                "logical_key": "P2_REFERENCE_CONDITION:ED2_B2_CONTINUOUS",
                "artifact_version": "1.0.0",
                "schema_version": "TPAA_P2_REFERENCE_CONDITION_V1",
                "payload": {
                    "schema": "TPAA_P2_REFERENCE_CONDITION_V1",
                    "factor_values": {"SESSION_CONTEXT_FACTOR": "0.5"},
                },
            },
            "attribution_spec": {
                "logical_key": "P2_ATTRIBUTION_SPEC:P2_LINEAR_REFERENCE_ADJUSTMENT",
                "artifact_version": "1.0.0",
                "schema_version": "TPAA_P2_ATTRIBUTION_SPEC_V1",
                "payload": {
                    "schema": "TPAA_P2_ATTRIBUTION_SPEC_V1",
                    "model_plugin": "LINEAR_REFERENCE_ADJUSTMENT",
                    "model_plugin_version": "1.0.0",
                    "uncertainty_method": "JACKKNIFE_LEAVE_ONE_INDEPENDENT_SUBJECT_OUT",
                    "uncertainty_level": "0.95",
                },
            },
        },
        "p3_profile": {
            "session_order_scope": {
                "scope_code": "ED2_B2_CONTINUOUS_P3",
                "scope_type": "AIRCRAFT_PROGRAM",
                "subject_kind": "AIRCRAFT",
                "selector_json": {
                    "aircraft_id": _AIRCRAFT_ID,
                    "qualification_scope": "ED2_B2_CONTINUOUS",
                },
                "selector_language_version": "1.0.0",
                "scope_revision": 1,
                "description": "ED2 B2 continuous production P3 qualification",
            },
            "configuration": {
                "aircraft_configuration_id": _id("configuration", 1),
                "effective_session_time_us": 0,
                "snapshot_json": {
                    "configuration_code": "ED2_B2_BASELINE",
                    "aircraft_id": _AIRCRAFT_ID,
                },
            },
            "as_of_utc": "2030-01-01T00:00:00Z",
            "training_created_at_utc": "2030-01-01T00:01:00Z",
            "trained_at_utc": "2030-01-01T00:02:00Z",
            "surface_created_at_utc": "2030-01-01T00:03:00Z",
            "twin_valid_from_utc": "2026-10-01T00:00:00Z",
            "twin_published_at_utc": "2030-01-01T00:04:00Z",
            "estimate_created_at_utc": "2030-01-01T00:05:00Z",
        },
        "p4_profile": {
            "actor_id": _id("actor", 1),
            "instructor_actor_id": _id("instructor", 1),
            "role_code": "SUBJECT_SELF",
            "seat_code": "FRONT",
            "function_code": "PILOT",
            "evidence_family": "OUTCOME_CONTEXT",
            "evidence_availability_status": "AVAILABLE",
            "confidence": "0.9",
            "created_at_utc": "2030-01-01T01:00:00Z",
        },
        "p5_profile": {
            "team_id": _id("team", 1),
            "objective_result_refs": [],
            "confidence": "0.8",
            "as_of_utc": "2030-01-01T02:00:00Z",
            "created_at_utc": "2030-01-01T02:01:00Z",
        },
        "p6_profile": {
            "target_scope": "SUBJECT",
            "subject_or_composition_ref": _AIRCRAFT_ID,
            "forecast_origin_utc": "2030-01-01T05:00:00Z",
            "as_of_utc": "2030-01-01T05:00:00Z",
            "trained_at_utc": "2030-01-01T05:01:00Z",
            "sealed_at_utc": "2030-01-01T05:02:00Z",
            "forecast": {
                "forecast_spec_id": "P6_FORECAST:P3_CAPABILITY_NEXT_SESSION",
                "forecast_spec_version": "1.0.0",
                "assumption_profile_id": "P6_ASSUMPTION:TRAINING_EVALUATION",
                "assumption_profile_version": "1.0.0",
            },
            "counterfactual": {
                "scenario_definition_id": _id("scenario", 1),
                "interventions": {
                    "training_focus": {
                        "type": "TRAINING_FOCUS",
                        "value": "DEBRIEF_REPEAT",
                    }
                },
                "held_fixed_assumptions": {
                    "configuration": "UNCHANGED"
                },
            },
        },
    }


def main() -> int:
    print(
        json.dumps(
            build_ed2_b2_continuous_qualification_plan(),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
