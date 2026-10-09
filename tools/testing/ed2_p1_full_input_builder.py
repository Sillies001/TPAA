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
from uuid import NAMESPACE_URL, UUID, uuid5

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
from tpaa_episode.production_stage import (
    PRODUCTION_STAGE_DETECTION_METHOD,
    PRODUCTION_STAGE_ORDER,
    PRODUCTION_STAGE_PRECEDENCE_SOURCE,
    PRODUCTION_STAGE_PROFILE_ID,
    PRODUCTION_STAGE_TERMINATOR,
)
from tpaa_ingest import (
    PRODUCTION_FLIGHT_ACTION_PROFILE_ID,
    PRODUCTION_FLIGHT_ACTION_SCHEMA,
    PRODUCTION_FLIGHT_MEDIA_TYPE,
    SourceFamily,
    descriptor_for_interchange_family,
    production_interchange_profile,
)
from tpaa_metric import (
    AIR_M1_IMPLEMENTATION,
    M2MetricExecutionPlan,
    build_m2_qa_inputs,
    build_m2_sns_accuracy_inputs,
    build_m2_sns_detection_inputs,
    build_m3_metric_execution_plan,
    serialize_m1_air_result,
)
from tpaa_runtime.production_p1_source_policy import (
    production_p1_required_source_families,
)
from tpaa_runtime.production_p1_transport import encode_production_p1_transport
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
    return sorted(products)


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


_SOURCE_NAMESPACE = UUID("735bb395-eb08-4c3f-9cc0-f78635fc37ec")
_DEFAULT_QUALIFICATION_FLIGHT = (
    ROOT
    / "docs"
    / "baseline"
    / "PRCB-1.0"
    / "qualification"
    / "PRCB_C2_NOMINAL_FLIGHT.json"
)


def _canonical_input_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _lineage_families(family: str) -> list[str]:
    return [
        item.value
        for item in sorted(
            production_p1_required_source_families(family),
            key=lambda item: item.value,
        )
    ]


def _source_id(session_id: str, family: SourceFamily, kind: str) -> str:
    return str(
        uuid5(
            _SOURCE_NAMESPACE,
            f"{session_id}|{family.value}|{kind}",
        )
    )


def _interchange_source_document(
    *,
    session_id: str,
    family: SourceFamily,
    metric_input_hashes: dict[str, str],
    ordinal: int,
    stage_projection: dict[str, object] | None = None,
) -> dict[str, object]:
    descriptor = descriptor_for_interchange_family(family)
    source_id = _source_id(session_id, family, "source")
    artifact_id = _source_id(session_id, family, "artifact")
    stream_id = _source_id(session_id, family, "stream")
    profile = production_interchange_profile(family)
    payload: dict[str, object] = {
        "projection_class": profile.projection_class,
        "qualification_only": True,
        "metric_input_hashes": metric_input_hashes,
    }
    if stage_projection is not None:
        if family is not SourceFamily.SCENARIO:
            raise ValueError("ED2_P1_STAGE_PROJECTION_FAMILY_INVALID")
        payload["stage_projection"] = stage_projection
    source_document = {
        "schema": "TPAA_PRODUCTION_INTERCHANGE_SOURCE_V1",
        "schema_version": "1.0.0",
        "source_family": family.value,
        "session_id": session_id,
        "profile": {
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
            "profile_hash": profile.profile_hash,
        },
        "knowledge_time_utc": "2026-10-08T00:00:00Z",
        "payload": payload,
    }
    return {
        "source_json": json.dumps(
            source_document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ),
        "source_import": {
            "source_family": family.value,
            "source_id": source_id,
            "session_id": session_id,
            "platform_id": None,
            "producer_system": "ED2_B1_QUALIFICATION_GATEWAY",
            "schema_name": "TPAA_PRODUCTION_INTERCHANGE_SOURCE_V1",
            "schema_version": "1.0.0",
            "time_basis": "SESSION_TIME_US",
            "nominal_rate_hz": None,
            "source_quality": "1.0",
            "source_stream_id": stream_id,
            "stream_code": f"{family.value}_QUALIFICATION",
            "ordinal_basis": "SOURCE_SEQUENCE",
            "stream_status": "ACTIVE",
            "artifact_id": artifact_id,
            "source_artifact_sequence": ordinal,
            "uri_kind": "MANAGED",
            "availability_status": "AVAILABLE",
            "last_verified_at": "2026-10-08T00:00:00Z",
            "mtime_source": None,
            "source_ref": f"qualification://ED2_B1/{family.value}",
            "media_type": descriptor.media_types[0],
            "classification_label": "UNCLASSIFIED",
        },
    }


def _qualification_stage_projection(
    flight_raw: Mapping[str, object],
) -> dict[str, object]:
    transform = flight_raw.get("time_transform")
    rows = flight_raw.get("rows")
    if not isinstance(transform, Mapping) or not isinstance(rows, list) or not rows:
        raise TypeError("ED2_P1_QUALIFICATION_STAGE_SOURCE_INVALID")
    scale_raw = transform.get("scale")
    offset_raw = transform.get("offset_us")
    if (
        isinstance(scale_raw, bool)
        or not isinstance(scale_raw, (int, float))
        or isinstance(offset_raw, bool)
        or not isinstance(offset_raw, int)
    ):
        raise TypeError("ED2_P1_QUALIFICATION_STAGE_TIME_INVALID")
    first = rows[0]
    last = rows[-1]
    if not isinstance(first, Mapping) or not isinstance(last, Mapping):
        raise TypeError("ED2_P1_QUALIFICATION_STAGE_ROW_INVALID")
    first_source = first.get("source_time_us")
    last_source = last.get("source_time_us")
    if (
        isinstance(first_source, bool)
        or not isinstance(first_source, int)
        or isinstance(last_source, bool)
        or not isinstance(last_source, int)
    ):
        raise TypeError("ED2_P1_QUALIFICATION_STAGE_TIME_INVALID")
    start = int(round(first_source * float(scale_raw))) + offset_raw
    end = int(round(last_source * float(scale_raw))) + offset_raw + 1
    span = end - start
    if span < 4:
        raise ValueError("ED2_P1_QUALIFICATION_STAGE_INTERVAL_TOO_SHORT")
    boundaries = [
        start,
        start + span // 4,
        start + span // 2,
        start + (3 * span) // 4,
        end,
    ]
    if any(
        left >= right
        for left, right in zip(boundaries, boundaries[1:], strict=False)
    ):
        raise ValueError("ED2_P1_QUALIFICATION_STAGE_INTERVAL_INVALID")
    markers = [
        {
            "marker": stage_type,
            "session_time_us": boundaries[index],
        }
        for index, stage_type in enumerate(PRODUCTION_STAGE_ORDER)
    ]
    markers.append(
        {
            "marker": PRODUCTION_STAGE_TERMINATOR,
            "session_time_us": boundaries[-1],
        }
    )
    return {
        "stage_profile_id": PRODUCTION_STAGE_PROFILE_ID,
        "precedence_source": PRODUCTION_STAGE_PRECEDENCE_SOURCE,
        "detection_method": PRODUCTION_STAGE_DETECTION_METHOD,
        "markers": markers,
    }


def _qualification_action_projection(
    *,
    session_id: str,
    stage_projection: Mapping[str, object],
) -> dict[str, object]:
    raw_markers = stage_projection.get("markers")
    if not isinstance(raw_markers, list) or len(raw_markers) < 2:
        raise TypeError("ED2_P1_QUALIFICATION_ACTION_STAGE_INVALID")
    first = raw_markers[0]
    last = raw_markers[-1]
    if not isinstance(first, Mapping) or not isinstance(last, Mapping):
        raise TypeError("ED2_P1_QUALIFICATION_ACTION_STAGE_INVALID")
    start = first.get("session_time_us")
    end = last.get("session_time_us")
    if (
        isinstance(start, bool)
        or not isinstance(start, int)
        or isinstance(end, bool)
        or not isinstance(end, int)
        or start >= end
    ):
        raise TypeError("ED2_P1_QUALIFICATION_ACTION_TIME_INVALID")
    return {
        "schema": PRODUCTION_FLIGHT_ACTION_SCHEMA,
        "profile_id": PRODUCTION_FLIGHT_ACTION_PROFILE_ID,
        "events": [
            {
                "action_event_id": _source_id(
                    session_id,
                    SourceFamily.FLIGHT,
                    "action-event",
                ),
                "action_type": "FLIGHT_CONTROL_ACTIVITY",
                "start_session_time_us": start,
                "end_session_time_us": end,
                "evidence_ref": "qualification://ED2_B1/FLIGHT/actions",
            }
        ],
    }


def _remap_system_identity(
    value: object,
    identities: Mapping[str, str],
) -> object:
    """Rebind only exact Mission-System identities, including nested plugin inputs."""

    if isinstance(value, str):
        return identities.get(value, value)
    if isinstance(value, list):
        return [_remap_system_identity(item, identities) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("ED2_QUALIFICATION_SYSTEM_MAPPING_INVALID")
        return {
            identities.get(key, key): _remap_system_identity(item, identities)
            for key, item in value.items()
        }
    return value


def build_full_p1_request_contract(
    *,
    aircraft_id: str,
    authority_root: Path = AUTHORITY,
    flight_source_json: str | None = None,
    system_id_namespace: UUID | None = None,
) -> dict[str, object]:
    """Return a JSON-safe six-source exact-116 qualification request contract."""

    inputs = build_full_p1_catalog_inputs(authority_root=authority_root)
    systems, bindings = build_full_p1_system_authority(
        inputs,
        authority_root=authority_root,
        aircraft_id=aircraft_id,
    )
    if system_id_namespace is not None:
        remapped_ids = {
            existing_id: str(uuid5(system_id_namespace, f"mission-system:{existing_id}"))
            for existing_id in systems
        }
        remapped_inputs: dict[str, dict[str, object]] = {}
        for metric_code, original_input in inputs.items():
            remapped = _remap_system_identity(original_input, remapped_ids)
            if not isinstance(remapped, dict) or not all(
                isinstance(key, str) for key in remapped
            ):
                raise TypeError("ED2_QUALIFICATION_SYSTEM_MAPPING_INVALID")
            remapped_inputs[metric_code] = cast(dict[str, object], remapped)
        inputs = remapped_inputs
        for metric_code, existing_id in bindings.items():
            if inputs[metric_code].get("mission_system_instance_id") != remapped_ids[
                existing_id
            ]:
                raise ValueError("ED2_QUALIFICATION_SYSTEM_INPUT_DRIFT")
        systems, bindings = build_full_p1_system_authority(
            inputs,
            authority_root=authority_root,
            aircraft_id=aircraft_id,
        )
    plan = build_m3_metric_execution_plan(authority_root)
    source_text = (
        _DEFAULT_QUALIFICATION_FLIGHT.read_text(encoding="utf-8")
        if flight_source_json is None
        else flight_source_json
    )
    flight_raw: object = json.loads(source_text)
    if not isinstance(flight_raw, dict):
        raise TypeError("ED2_P1_QUALIFICATION_FLIGHT_INVALID")
    session_id = flight_raw.get("session_id")
    source_aircraft = flight_raw.get("aircraft_id")
    if not isinstance(session_id, str) or not isinstance(source_aircraft, str):
        raise TypeError("ED2_P1_QUALIFICATION_FLIGHT_IDENTITY_INVALID")
    if source_aircraft != aircraft_id:
        raise ValueError("ED2_P1_QUALIFICATION_AIRCRAFT_DRIFT")

    stage_projection = _qualification_stage_projection(
        cast(Mapping[str, object], flight_raw)
    )

    flight_raw["action_projection"] = _qualification_action_projection(
        session_id=session_id,
        stage_projection=stage_projection,
    )
    source_text = json.dumps(
        flight_raw,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )

    metric_lineage = {
        definition.metric_code: _lineage_families(definition.family)
        for definition in plan.definitions
    }
    input_hashes = {
        code: _canonical_input_hash(inputs[code])
        for code in plan.metric_codes
    }
    family_metric_hashes = {
        family.value: {
            code: input_hashes[code]
            for code in sorted(
                code
                for code, families in metric_lineage.items()
                if family.value in families
            )
        }
        for family in SourceFamily
    }
    source_documents: list[dict[str, object]] = [
        {
            "source_json": source_text,
            "source_import": {
                "source_family": "FLIGHT",
                "source_id": _source_id(session_id, SourceFamily.FLIGHT, "source"),
                "session_id": session_id,
                "platform_id": None,
                "producer_system": "PRCB_C5_INSTALLED_QUALIFICATION",
                "schema_name": "TPAA_PRODUCTION_FLIGHT_SOURCE_V1",
                "schema_version": "1.0.0",
                "time_basis": "SOURCE_US",
                "nominal_rate_hz": "10.0",
                "source_quality": "1.0",
                "source_stream_id": _source_id(
                    session_id,
                    SourceFamily.FLIGHT,
                    "stream",
                ),
                "stream_code": "FLIGHT_PRIMARY",
                "ordinal_basis": "SOURCE_SEQUENCE",
                "stream_status": "ACTIVE",
                "artifact_id": _source_id(
                    session_id,
                    SourceFamily.FLIGHT,
                    "artifact",
                ),
                "source_artifact_sequence": 0,
                "uri_kind": "EXTERNAL_FILE",
                "availability_status": "AVAILABLE",
                "last_verified_at": "2026-10-08T00:00:00Z",
                "mtime_source": None,
                "source_ref": "qualification://PRCB_C2_NOMINAL_FLIGHT",
                "media_type": PRODUCTION_FLIGHT_MEDIA_TYPE,
                "classification_label": "UNCLASSIFIED",
                "session_code": "ED2-B1-FULL-P1",
                "session_type": "SIM",
            },
        }
    ]
    for ordinal, family in enumerate(
        (
            SourceFamily.MISSION_AVIONICS,
            SourceFamily.TDL,
            SourceFamily.RANGE_ACMI,
            SourceFamily.SCENARIO,
            SourceFamily.AUDIO_VIDEO,
        ),
        start=1,
    ):
        source_documents.append(
            _interchange_source_document(
                session_id=session_id,
                family=family,
                metric_input_hashes=family_metric_hashes[family.value],
                ordinal=ordinal,
                stage_projection=(
                    stage_projection
                    if family is SourceFamily.SCENARIO
                    else None
                ),
            )
        )

    transport_inputs = encode_production_p1_transport(
        inputs,
        field="p1_catalog_inputs",
    )
    if not isinstance(transport_inputs, dict) or not all(
        isinstance(key, str) for key in transport_inputs
    ):
        raise TypeError("ED2_P1_REQUEST_TRANSPORT_INVALID")

    payload: dict[str, object] = {
        "schema": "TPAA_ED2_B1_FULL_P1_REQUEST_CONTRACT_V1",
        "source_documents": source_documents,
        "metric_input_source_families": metric_lineage,
        "p1_catalog_inputs": transport_inputs,
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
