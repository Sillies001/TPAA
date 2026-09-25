"""M2-WORLD-002 RADAR sensor World product.

This module projects governed M2-DATA-003 mission-system identity and
M2-DATA-004 measurement/reference alignment into one Core 1.6.0 compatible
MACHINE World product. It preserves the frozen P1-SNS-* RADAR applicability
boundary and never fabricates a master.entity subject id when no governed
mission-system-to-entity mapping exists.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID, uuid5

from tpaa_ingest import (
    M2MeasurementAlignmentProjection,
    M2MissionSystemProjection,
    MeasurementAlignmentRow,
    load_m2_measurement_alignment,
    load_m2_mission_system,
)

from .m2_reference_time import CORE_WORLD_MANIFEST_FIELDS, CoreWorldManifest

CORE_SCHEMA_VERSION = "1.6.0"
CORE_WORLD_TABLE = "world.world_product_manifest"
WORLD_POLICY_ID = "WORLD_CAPABILITY_REGISTRY"
WORLD_POLICY_VERSION = "1.0.0"
RADAR_WORLD_KIND = "MACHINE"
RADAR_WORLD_VERSION = "M2_RADAR_SENSOR_WORLD_V1"
SNS_FAMILY = "P1-SNS-*"
SNS_SUBJECT_TYPE = "MISSION_SYSTEM_INSTANCE"
SNS_APPLICABILITY_MODE = "SYSTEM_TYPE_EXACT"
SNS_ALLOWED_SYSTEM_TYPES = ("RADAR",)
SNS_CODES = tuple(f"P1-SNS-{index:03d}" for index in range(1, 22))
REQUIRED_SNS_AUTHORITIES = frozenset(
    {
        "CANONICAL_MISSION_SYSTEM_MEASUREMENT_V1",
        "CONTRACT_DETECTION_CONFIRMATION_EVENT_V1",
        "CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1",
        "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1",
        "CONTRACT_REFERENCE_RELATIVE_STATE_V1",
    }
)
RADAR_WORLD_NAMESPACE = UUID("ef4a4b61-f394-4a39-b14b-662447229413")


class M2RadarSensorWorldError(RuntimeError):
    """Deterministic fail-closed M2 RADAR sensor World error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class M2RadarSensorWorld:
    """Core-compatible RADAR MACHINE World plus its governed upstream inputs."""

    manifest: CoreWorldManifest
    mission_system: M2MissionSystemProjection
    measurement_alignment: M2MeasurementAlignmentProjection
    subject_type: str
    mission_system_instance_id: str
    applicability_mode: str
    allowed_system_types: tuple[str, ...]
    core_schema_sha256: str
    world_policy_sha256: str
    metric_catalog_sha256: str
    metric_input_authority_sha256: str
    logical_hash: str
    shadow_schema_created: bool = False
    metric_logic_executed: bool = False
    stage_projection_executed: bool = False
    persistence_executed: bool = False
    observation_projection_executed: bool = False
    release_publication_executed: bool = False
    detection_opportunity_rebuilt: bool = False
    detection_confirmation_rebuilt: bool = False


def _load_object(path: Path, *, code: str) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M2RadarSensorWorldError(code, f"{path.as_posix()}: {exc}") from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise M2RadarSensorWorldError(code, f"{path.as_posix()}: root must be object")
    return cast(dict[str, object], raw)


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_AUTHORITY_INVALID",
            f"{field} must be string-keyed object",
        )
    return cast(dict[str, object], value)


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_AUTHORITY_MISSING",
            path.as_posix(),
        ) from exc


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _canonical_uuid(value: str, *, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_UUID_INVALID",
            f"{field}={value!r}",
        ) from exc
    canonical = str(parsed)
    if parsed.int == 0 or canonical != value:
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_UUID_INVALID",
            f"{field}={value!r}",
        )
    return canonical


def _validate_authority(
    authority_root: Path,
) -> tuple[str, str, str, str, str]:
    core_path = authority_root / "CORE_LOGICAL_MODEL.json"
    policy_path = authority_root / "WORLD_CAPABILITY_REGISTRY.json"
    catalog_path = authority_root / "P1_METRIC_CATALOG.json"
    matrix_path = authority_root / "METRIC_INPUT_AUTHORITY_MATRIX.json"

    core = _load_object(core_path, code="M2_RADAR_WORLD_CORE_AUTHORITY_INVALID")
    policy = _load_object(policy_path, code="M2_RADAR_WORLD_POLICY_AUTHORITY_INVALID")
    catalog = _load_object(catalog_path, code="M2_RADAR_WORLD_CATALOG_AUTHORITY_INVALID")
    matrix = _load_object(matrix_path, code="M2_RADAR_WORLD_INPUT_AUTHORITY_INVALID")

    if core.get("db_schema_version") != CORE_SCHEMA_VERSION:
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_CORE_SCHEMA_VERSION_MISMATCH",
            repr(core.get("db_schema_version")),
        )
    tables = _object(core.get("tables"), field="CORE_LOGICAL_MODEL.tables")
    table = _object(tables.get(CORE_WORLD_TABLE), field=CORE_WORLD_TABLE)
    raw_fields = table.get("fields")
    if not isinstance(raw_fields, list):
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_CORE_MANIFEST_INVALID",
            "fields must be list",
        )
    field_names: list[str] = []
    for index, raw_field in enumerate(raw_fields):
        field = _object(raw_field, field=f"{CORE_WORLD_TABLE}.fields[{index}]")
        name = field.get("name")
        if not isinstance(name, str) or not name:
            raise M2RadarSensorWorldError(
                "M2_RADAR_WORLD_CORE_MANIFEST_INVALID",
                f"fields[{index}].name",
            )
        field_names.append(name)
    if tuple(field_names) != CORE_WORLD_MANIFEST_FIELDS:
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_CORE_MANIFEST_DRIFT",
            repr(field_names),
        )

    if policy.get("registry_id") != WORLD_POLICY_ID:
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_POLICY_ID_MISMATCH",
            repr(policy.get("registry_id")),
        )
    if policy.get("version") != WORLD_POLICY_VERSION:
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_POLICY_VERSION_MISMATCH",
            repr(policy.get("version")),
        )
    worlds = _object(policy.get("worlds"), field="WORLD_CAPABILITY_REGISTRY.worlds")
    if not isinstance(worlds.get("M"), str):
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_MACHINE_SEMANTIC_MISSING",
            "WORLD_CAPABILITY_REGISTRY.worlds.M",
        )

    family_contracts = _object(
        catalog.get("family_applicability_contracts"),
        field="P1_METRIC_CATALOG.family_applicability_contracts",
    )
    sns_contract = _object(family_contracts.get(SNS_FAMILY), field=SNS_FAMILY)
    expected_contract = {
        "subject_type": SNS_SUBJECT_TYPE,
        "applicability_mode": SNS_APPLICABILITY_MODE,
        "allowed_system_types": list(SNS_ALLOWED_SYSTEM_TYPES),
        "family_meaning": (
            "RADAR sensor detection and measurement layer; "
            "not generic sensor performance"
        ),
    }
    if sns_contract != expected_contract:
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_SNS_APPLICABILITY_DRIFT",
            repr(sns_contract),
        )

    raw_metrics = catalog.get("metrics")
    if not isinstance(raw_metrics, list):
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_CATALOG_AUTHORITY_INVALID",
            "metrics must be list",
        )
    sns_metrics: list[dict[str, object]] = []
    for index, raw_metric in enumerate(raw_metrics):
        metric = _object(raw_metric, field=f"P1_METRIC_CATALOG.metrics[{index}]")
        code = metric.get("metric_code")
        if isinstance(code, str) and code.startswith("P1-SNS-"):
            sns_metrics.append(metric)
    codes = tuple(str(metric.get("metric_code")) for metric in sns_metrics)
    if codes != SNS_CODES:
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_SNS_METRIC_SET_DRIFT",
            repr(codes),
        )
    for metric in sns_metrics:
        if (
            metric.get("subject_type") != SNS_SUBJECT_TYPE
            or metric.get("delivery_milestone") != "M2"
            or metric.get("delivery_batch") != "P1_FOUNDATION_32"
        ):
            raise M2RadarSensorWorldError(
                "M2_RADAR_WORLD_SNS_METRIC_AUTHORITY_DRIFT",
                repr(metric.get("metric_code")),
            )

    raw_bindings = matrix.get("bindings")
    if not isinstance(raw_bindings, list):
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_INPUT_AUTHORITY_INVALID",
            "bindings must be list",
        )
    sns_binding_codes: set[str] = set()
    sns_authorities: set[str] = set()
    for index, raw_binding in enumerate(raw_bindings):
        binding = _object(raw_binding, field=f"METRIC_INPUT_AUTHORITY_MATRIX.bindings[{index}]")
        code = binding.get("metric_code")
        if isinstance(code, str) and code.startswith("P1-SNS-"):
            sns_binding_codes.add(code)
            authority_id = binding.get("authority_id")
            if isinstance(authority_id, str):
                sns_authorities.add(authority_id)
    if sns_binding_codes != set(SNS_CODES):
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_SNS_BINDING_SET_DRIFT",
            repr(sorted(sns_binding_codes)),
        )
    if not REQUIRED_SNS_AUTHORITIES.issubset(sns_authorities):
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_SNS_AUTHORITY_SET_INCOMPLETE",
            repr(sorted(sns_authorities)),
        )

    return (
        _sha256_file(core_path),
        _sha256_file(policy_path),
        _sha256_file(catalog_path),
        _sha256_file(matrix_path),
        f"{WORLD_POLICY_ID}:{WORLD_POLICY_VERSION}",
    )


def _row_payload(row: MeasurementAlignmentRow) -> dict[str, object]:
    measurement = row
    return {
        "measurement_id": measurement.measurement_id,
        "reference_state_id": measurement.reference_state_id,
        "mission_system_instance_id": measurement.mission_system_instance_id,
        "target_pair_id": measurement.target_pair_id,
        "measurement_time_us": measurement.measurement_time_us,
        "reference_time_us": measurement.reference_time_us,
        "gap_us": measurement.gap_us,
        "match_status": measurement.match_status,
        "measured_range_m": measurement.measured_range_m,
        "reference_range_m": measurement.reference_range_m,
        "measured_az_rad": measurement.measured_az_rad,
        "reference_az_rad": measurement.reference_az_rad,
        "measured_el_rad": measurement.measured_el_rad,
        "reference_el_rad": measurement.reference_el_rad,
        "measured_position_ecef_m": measurement.measured_position_ecef_m,
        "reference_target_position_ecef_m": (
            measurement.reference_target_position_ecef_m
        ),
        "measured_radial_velocity_mps": measurement.measured_radial_velocity_mps,
        "reference_range_rate_mps": measurement.reference_range_rate_mps,
        "measured_position_sensor_frame": measurement.measured_position_sensor_frame,
        "reference_position_sensor_frame": measurement.reference_position_sensor_frame,
        "measured_position_local": measurement.measured_position_local,
        "reference_position_local": measurement.reference_position_local,
        "sensor_measurement": dict(measurement.sensor_measurement),
        "reference_relative_state": dict(measurement.reference_relative_state),
        "residual_unit": measurement.residual_unit,
        "error_domain": measurement.error_domain,
        "measurement_error": measurement.measurement_error,
        "reference_uncertainty": measurement.reference_uncertainty,
        "alignment_uncertainty": measurement.alignment_uncertainty,
        "sensor_measurement_uncertainty": (
            measurement.sensor_measurement_uncertainty
        ),
        "reference_truth_uncertainty": measurement.reference_truth_uncertainty,
        "uncertainty_provenance": dict(measurement.uncertainty_provenance),
    }


def _world_payload(
    mission: M2MissionSystemProjection,
    alignment: M2MeasurementAlignmentProjection,
) -> dict[str, object]:
    instance = mission.instance
    return {
        "session_id": alignment.session_id,
        "subject": {
            "subject_type": mission.subject_type,
            "mission_system_instance_id": instance.mission_system_instance_id,
            "identity_ref": mission.identity.identity_ref,
            "source_entity_key": mission.identity.source_entity_key,
            "aircraft_id": instance.aircraft_id,
            "system_type": instance.system_type,
            "system_code": instance.system_code,
            "hardware_version": instance.hardware_version,
            "software_version": instance.software_version,
            "installation_id": instance.installation_id,
            "alignment_profile_version": instance.alignment_profile_version,
            "configuration_hash": instance.configuration_hash,
            "status": instance.status,
        },
        "applicability": {
            "metric_family": mission.metric_family,
            "applicability_mode": mission.applicability_mode,
            "allowed_system_types": mission.allowed_system_types,
            "sns_applicable": mission.sns_applicable,
        },
        "measurement_alignment": {
            "fixture_id": alignment.fixture_id,
            "fixture_version": alignment.fixture_version,
            "target_pair_id": alignment.target_pair_id,
            "quality_profile": {
                "profile_id": alignment.quality_profile.profile_id,
                "profile_version": alignment.quality_profile.profile_version,
                "profile_hash": alignment.quality_profile.profile_hash,
                "max_gap_us": alignment.quality_profile.max_gap_us,
                "min_coverage": alignment.quality_profile.min_coverage,
            },
            "coverage": alignment.coverage,
            "max_observed_gap_us": alignment.max_observed_gap_us,
            "status": alignment.status,
            "reason_codes": alignment.reason_codes,
            "rows": [_row_payload(row) for row in alignment.rows],
            "upstream_logical_hash": alignment.logical_hash,
        },
        "upstream": {
            "mission_system_logical_hash": mission.logical_hash,
            "mission_system_input_sha256": mission.input_sha256,
            "measurement_alignment_logical_hash": alignment.logical_hash,
            "measurement_alignment_input_sha256": alignment.input_sha256,
        },
    }


def build_m2_radar_sensor_world(
    mission: M2MissionSystemProjection,
    alignment: M2MeasurementAlignmentProjection,
    *,
    authority_root: Path,
    release_id: str,
) -> M2RadarSensorWorld:
    """Build a replay-stable RADAR MACHINE World from governed M2 inputs."""

    canonical_release_id = _canonical_uuid(release_id, field="release_id")
    subject_id = mission.instance.mission_system_instance_id
    _canonical_uuid(subject_id, field="mission_system_instance_id")
    _canonical_uuid(alignment.session_id, field="session_id")
    _canonical_uuid(mission.instance.aircraft_id, field="aircraft_id")

    if (
        mission.subject_type != SNS_SUBJECT_TYPE
        or mission.metric_family != SNS_FAMILY
        or mission.applicability_mode != SNS_APPLICABILITY_MODE
        or mission.allowed_system_types != SNS_ALLOWED_SYSTEM_TYPES
        or mission.instance.system_type not in SNS_ALLOWED_SYSTEM_TYPES
        or not mission.sns_applicable
    ):
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_APPLICABILITY_DRIFT",
            repr(mission),
        )
    if alignment.mission_system_instance_id != subject_id:
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_SUBJECT_DRIFT",
            (
                f"alignment={alignment.mission_system_instance_id} "
                f"mission={subject_id}"
            ),
        )
    if alignment.mission_system_logical_hash != mission.logical_hash:
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_MISSION_PROVENANCE_DRIFT",
            (
                f"alignment={alignment.mission_system_logical_hash} "
                f"mission={mission.logical_hash}"
            ),
        )
    if not alignment.rows:
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_ALIGNMENT_EMPTY",
            alignment.fixture_id,
        )
    if alignment.status not in {"READY", "INSUFFICIENT"}:
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_ALIGNMENT_STATUS_INVALID",
            alignment.status,
        )

    (
        core_hash,
        policy_hash,
        catalog_hash,
        input_authority_hash,
        policy_version,
    ) = _validate_authority(authority_root)

    payload = _world_payload(mission, alignment)
    logical_content_hash = _canonical_hash(payload)
    start = min(
        min(row.measurement_time_us, row.reference_time_us)
        for row in alignment.rows
    )
    end = max(
        max(row.measurement_time_us, row.reference_time_us)
        for row in alignment.rows
    )
    if end <= start:
        raise M2RadarSensorWorldError(
            "M2_RADAR_WORLD_TIME_RANGE_INVALID",
            f"start={start} end={end}",
        )

    status = "READY" if alignment.status == "READY" else "PARTIAL"
    source_signature = _canonical_hash(
        {
            "mission_system_logical_hash": mission.logical_hash,
            "measurement_alignment_logical_hash": alignment.logical_hash,
            "core_schema_sha256": core_hash,
            "world_policy_sha256": policy_hash,
            "metric_catalog_sha256": catalog_hash,
            "metric_input_authority_sha256": input_authority_hash,
        }
    )
    request_hash = _canonical_hash(
        {
            "release_id": canonical_release_id,
            "session_id": alignment.session_id,
            "mission_system_instance_id": subject_id,
            "world_kind": RADAR_WORLD_KIND,
            "world_version": RADAR_WORLD_VERSION,
            "logical_content_hash": logical_content_hash,
            "policy_version": policy_version,
        }
    )
    world_product_id = str(
        uuid5(
            RADAR_WORLD_NAMESPACE,
            _canonical_bytes(
                {
                    "release_id": canonical_release_id,
                    "session_id": alignment.session_id,
                    "mission_system_instance_id": subject_id,
                    "world_version": RADAR_WORLD_VERSION,
                    "logical_content_hash": logical_content_hash,
                }
            ).decode("ascii"),
        )
    )
    manifest = CoreWorldManifest(
        world_product_id=world_product_id,
        release_id=canonical_release_id,
        session_id=alignment.session_id,
        episode_id=None,
        stage_id=None,
        world_kind=RADAR_WORLD_KIND,
        subject_id=None,
        observer_id=None,
        actor_id=None,
        aircraft_id=mission.instance.aircraft_id,
        aircraft_instance_id=None,
        dataset_id=None,
        start_session_time_us=start,
        end_session_time_us=end,
        status=status,
        coverage=alignment.coverage,
        confidence=1.0,
        reason_codes=alignment.reason_codes,
        source_authority_signature=source_signature,
        world_version=RADAR_WORLD_VERSION,
        policy_version=policy_version,
        artifact_sha256=logical_content_hash,
        logical_content_hash=logical_content_hash,
        request_hash=request_hash,
        supersedes_id=None,
    )
    logical_hash = _canonical_hash(
        {
            "session_id": alignment.session_id,
            "mission_system_instance_id": subject_id,
            "logical_content_hash": logical_content_hash,
            "core_schema_sha256": core_hash,
            "world_policy_sha256": policy_hash,
            "metric_catalog_sha256": catalog_hash,
            "metric_input_authority_sha256": input_authority_hash,
        }
    )
    return M2RadarSensorWorld(
        manifest=manifest,
        mission_system=mission,
        measurement_alignment=alignment,
        subject_type=SNS_SUBJECT_TYPE,
        mission_system_instance_id=subject_id,
        applicability_mode=SNS_APPLICABILITY_MODE,
        allowed_system_types=SNS_ALLOWED_SYSTEM_TYPES,
        core_schema_sha256=core_hash,
        world_policy_sha256=policy_hash,
        metric_catalog_sha256=catalog_hash,
        metric_input_authority_sha256=input_authority_hash,
        logical_hash=logical_hash,
    )


def project_m2_radar_sensor_world(
    mission_bundle: Path,
    alignment_bundle: Path,
    *,
    authority_root: Path,
    release_id: str,
) -> M2RadarSensorWorld:
    """Load governed RADAR inputs and build the M2-WORLD-002 product."""

    return build_m2_radar_sensor_world(
        load_m2_mission_system(mission_bundle),
        load_m2_measurement_alignment(alignment_bundle),
        authority_root=authority_root,
        release_id=release_id,
    )
