"""ED-2.0 full-116 P1 qualification input assembly.

This module is qualification/test support only.  Production runtime accepts the
resulting governed JSON payload but never imports this module or test fixtures.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, uuid5

from tools.testing.m2_air_formal_delivery_check import _runtime as _air_runtime
from tools.testing.m2_sns_detection_check import _contracts
from tools.testing.m3_air_remainder_check import _golden_inputs as _air_remainder_inputs
from tools.testing.m3_datalink_remainder_check import (
    _golden_inputs as _datalink_inputs,
)
from tools.testing.m3_esm_remainder_check import _golden_inputs as _esm_inputs
from tools.testing.m3_fusion_remainder_check import _golden_inputs as _fusion_inputs
from tools.testing.m3_identification_remainder_check import (
    _golden_inputs as _identification_inputs,
)
from tools.testing.m3_passive_remainder_check import _golden_inputs as _passive_inputs
from tools.testing.m3_track_remainder_check import _golden_inputs as _track_inputs
from tpaa_metric import (
    AIR_M1_IMPLEMENTATION,
    M2MetricExecutionPlan,
    build_m2_qa_inputs,
    build_m2_sns_accuracy_inputs,
    build_m2_sns_detection_inputs,
    build_m3_metric_execution_plan,
    serialize_m1_air_result,
)
from tpaa_world import project_m2_stage_world_lineage

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
M1_FIXTURES = ROOT / "tests" / "fixtures" / "m1"
M2_FIXTURES = ROOT / "tests" / "fixtures" / "m2"
_STAGE_WORLD_RELEASE_ID = "e2f10000-0000-4000-8000-000000000001"
_AIR_RELEASE_ID = "e2f10000-0000-4000-8000-000000000002"


def _plain(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("ED2 qualification mapping keys must be strings")
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_plain(item) for item in value]
    raise TypeError(
        f"ED2 qualification value is not JSON transportable: {type(value).__name__}"
    )


def _merge(
    target: dict[str, dict[str, object]],
    source: Mapping[str, Mapping[str, object]],
    *,
    label: str,
) -> None:
    for code, payload in source.items():
        if code in target:
            raise ValueError(f"ED2_P1_INPUT_DUPLICATE:{label}:{code}")
        plain = _plain(payload)
        if not isinstance(plain, dict) or not all(
            isinstance(key, str) for key in plain
        ):
            raise TypeError(f"ED2_P1_INPUT_INVALID:{label}:{code}")
        target[code] = cast(dict[str, object], plain)


def _required_products(
    plan: M2MetricExecutionPlan,
    prefix: str,
) -> list[str]:
    products = {
        definition.applicability.required_product_semantics
        for definition in plan.definitions
        if definition.metric_code.startswith(prefix)
        and definition.applicability.required_product_semantics is not None
    }
    return sorted(cast(set[str], products))


def build_full_p1_catalog_inputs(
    *,
    authority_root: Path = AUTHORITY,
) -> dict[str, dict[str, object]]:
    """Assemble one JSON-safe positive input for every frozen P1 definition."""

    plan = build_m3_metric_execution_plan(authority_root)
    result: dict[str, dict[str, object]] = {}

    stage_world = project_m2_stage_world_lineage(
        M1_FIXTURES / "BF_M1_NOMINAL_V1",
        M2_FIXTURES / "RT_M2_NOMINAL_V1",
        M2_FIXTURES / "TA_M2_NOMINAL_V1",
        M2_FIXTURES / "MSI_M2_RADAR_V1",
        M2_FIXTURES / "MA_M2_NOMINAL_V1",
        authority_root=authority_root,
        release_id=_STAGE_WORLD_RELEASE_ID,
    )
    radar_world = stage_world.radar_sensor_world
    qa = build_m2_qa_inputs(stage_world.reference_time_world, radar_world)
    _merge(result, qa, label="QA")

    contracts = _contracts(radar_world.mission_system_instance_id)
    detection = build_m2_sns_detection_inputs(
        radar_world,
        stage_world,
        opportunities=contracts["opportunities"],
        confirmations=contracts["confirmations"],
        target_presence_intervals=contracts["target_presence_intervals"],
        reference_range_samples=contracts["reference_range_samples"],
    )
    _merge(result, detection, label="SNS_DETECTION")

    associations = {
        row.measurement_id: {
            "association_id": f"assoc::{row.measurement_id}",
            "association_provenance": "ed2-full-116:v1",
            "association_valid": True,
            "reference_quality_status": "ACCEPTED",
        }
        for row in radar_world.measurement_alignment.rows
    }
    accuracy = build_m2_sns_accuracy_inputs(
        radar_world,
        stage_world,
        associations=associations,
    )
    _merge(result, accuracy, label="SNS_ACCURACY")

    _bundle, air_world, air_context, air_delivery = _air_runtime(
        "BF_M1_NOMINAL_V1",
        release_id=_AIR_RELEASE_ID,
    )
    air_foundation: dict[str, dict[str, object]] = {}
    for metric_result in air_delivery.metric_batch.results:
        air_foundation[metric_result.metric_code] = {
            "m1_result": serialize_m1_air_result(
                metric_result,
                metric_context_id=air_context.metric_context_id,
                world_product_id=air_world.world_product_id,
            ),
            "implementation_reuse": AIR_M1_IMPLEMENTATION,
        }
    _merge(result, air_foundation, label="AIR_FOUNDATION")
    _merge(result, _air_remainder_inputs(), label="AIR_REMAINDER")

    _merge(
        result,
        _track_inputs(_required_products(plan, "P1-TRK-")),
        label="TRACK",
    )
    _merge(
        result,
        _identification_inputs(_required_products(plan, "P1-ID-")),
        label="IDENTIFICATION",
    )
    _merge(result, _passive_inputs("IRST"), label="PASSIVE")
    _merge(result, _esm_inputs("RWR"), label="ESM")
    _merge(result, _datalink_inputs("DATALINK"), label="DATALINK")
    _merge(result, _fusion_inputs("FUSION"), label="FUSION")

    expected = set(plan.metric_codes)
    observed = set(result)
    if observed != expected:
        raise ValueError(
            "ED2_P1_INPUT_MEMBERSHIP_DRIFT:"
            f"missing={sorted(expected - observed)!r};"
            f"extra={sorted(observed - expected)!r}"
        )

    ordered = {code: result[code] for code in plan.metric_codes}
    encoded = json.dumps(
        ordered,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    restored: object = json.loads(encoded)
    if not isinstance(restored, dict):
        raise TypeError("ED2_P1_INPUT_JSON_ROUND_TRIP_INVALID")
    return cast(dict[str, dict[str, object]], restored)


def build_full_p1_system_authority(
    inputs: Mapping[str, Mapping[str, object]],
    *,
    authority_root: Path = AUTHORITY,
    aircraft_id: str,
) -> tuple[
    dict[str, dict[str, object]],
    dict[str, str],
]:
    """Build deterministic test-only DB 1.9 system rows and metric bindings."""

    plan = build_m3_metric_execution_plan(authority_root)
    systems: dict[str, dict[str, object]] = {}
    bindings: dict[str, str] = {}
    for definition in plan.definitions:
        if definition.subject_type != "MISSION_SYSTEM_INSTANCE":
            continue
        payload = inputs[definition.metric_code]
        existing_id = payload.get("mission_system_instance_id")
        if isinstance(existing_id, str):
            system_id = existing_id
        else:
            system_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"ed2-full-116-system:{definition.metric_code}",
                )
            )
        raw_type = payload.get("system_type")
        if isinstance(raw_type, str):
            system_type = raw_type
        elif definition.allowed_mission_system_types:
            system_type = definition.allowed_mission_system_types[0]
        else:
            raise ValueError(
                f"ED2_P1_SYSTEM_TYPE_UNRESOLVED:{definition.metric_code}"
            )
        prior = systems.get(system_id)
        if prior is not None and prior["system_type"] != system_type:
            raise ValueError(
                "ED2_P1_SYSTEM_TYPE_CONFLICT:"
                f"{system_id}:{prior['system_type']}:{system_type}"
            )
        bindings[definition.metric_code] = system_id
        if prior is None:
            systems[system_id] = {
                "mission_system_instance_id": system_id,
                "aircraft_id": aircraft_id,
                "system_type": system_type,
                "system_code": f"ED2-{system_type}-{system_id[:8]}",
                "hardware_version": "QUALIFICATION",
                "software_version": "QUALIFICATION",
                "installation_id": f"QUAL-{system_id[:12]}",
                "alignment_profile_version": "ED2-ALIGNMENT-V1",
                "status": "ACTIVE",
                "configuration_hash": hashlib.sha256(
                    system_id.encode("ascii")
                ).hexdigest(),
                "reference_truth_profile_version": "ED2-REFERENCE-V1",
                "reference_quality_status": "AVAILABLE",
                "reference_uncertainty_summary": {"status": "BOUNDED"},
                "alignment_uncertainty_summary": {"status": "BOUNDED"},
                "context_tags": {
                    "qualification": "ED2_FULL_116",
                    "system_type": system_type,
                },
            }
    return systems, bindings


def build_full_p1_request_contract(
    *,
    aircraft_id: str,
    authority_root: Path = AUTHORITY,
) -> dict[str, object]:
    """Return JSON-safe exact-116 inputs plus exact system authority bindings."""

    inputs = build_full_p1_catalog_inputs(authority_root=authority_root)
    systems, bindings = build_full_p1_system_authority(
        inputs,
        authority_root=authority_root,
        aircraft_id=aircraft_id,
    )
    payload: dict[str, object] = {
        "schema": "TPAA_ED2_B1_FULL_P1_REQUEST_CONTRACT_V1",
        "p1_catalog_inputs": inputs,
        "mission_system_instances": systems,
        "metric_system_bindings": bindings,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    restored: object = json.loads(encoded)
    if not isinstance(restored, dict) or not all(
        isinstance(key, str) for key in restored
    ):
        raise TypeError("ED2_P1_REQUEST_CONTRACT_JSON_INVALID")
    return cast(dict[str, object], restored)
