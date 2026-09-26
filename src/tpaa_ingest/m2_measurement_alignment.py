"""M2-DATA-004 measurement/reference alignment and quality projection.

This module binds governed RADAR measurement inputs to governed reference-relative
truth inputs and preserves the exact quality/coverage/gap/uncertainty provenance
required by P1-QA-006 and P1-SNS-005..021. It does not compute Metrics, Stage
products, database rows, Release products, or publication artifacts.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

from tpaa_ingest.m2_mission_system import load_m2_mission_system
from tpaa_ingest.m2_reference_truth import load_m2_reference_truth

EXPECTED_FIXTURE_IDS = frozenset(
    {
        "MA_M2_NOMINAL_V1",
        "MA_M2_GAP_V1",
        "MA_M2_WRAP_BOUNDARY_V1",
        "MA_M2_INSUFFICIENT_V1",
    }
)
EXPECTED_FIXTURE_VERSION = "1.0.0"
EXPECTED_MANIFEST_SCHEMA = "TPAA_M2_MEASUREMENT_ALIGNMENT_FIXTURE_V1"
EXPECTED_SOURCE_SCHEMA = "TPAA_M2_MEASUREMENT_ALIGNMENT_SOURCE_V1"
EXPECTED_CLASSIFICATION = "SYNTHETIC"
EXPECTED_HASH_ALGORITHM = "SHA256_PATH_SHA256_V1"
EXPECTED_SOURCE_RELATIVE_PATH = "source/measurement-alignment.json"
EXPECTED_CORE_BASELINE = "CB-1.4.0"
EXPECTED_REFERENCE_FIXTURE = "RT_M2_NOMINAL_V1"
EXPECTED_MISSION_SYSTEM_FIXTURE = "MSI_M2_RADAR_V1"
EXPECTED_MEASUREMENT_AUTHORITY = "CANONICAL_MISSION_SYSTEM_MEASUREMENT_V1"
EXPECTED_REFERENCE_AUTHORITY = "CANONICAL_REFERENCE_NAVIGATION_V1"
EXPECTED_REFERENCE_RELATIVE_STATE_CONTRACT = "CONTRACT_REFERENCE_RELATIVE_STATE_V1"
EXPECTED_REFERENCE_MATCH_QUALITY_CONTRACT = "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1"
EXPECTED_REFERENCE_MATCH_QUALITY_PROFILE_ID = "M2_REFERENCE_MATCH_QUALITY_V1"
EXPECTED_REFERENCE_MATCH_QUALITY_PROFILE_VERSION = "1.1.0"
EXPECTED_REFERENCE_MATCH_QUALITY_PROFILE_SHA256 = (
    "904100e467f10e89aca1f06b1e9eeff86923121063ec9a41a2d73f84cc2400f1"
)
EXPECTED_METRIC_INPUT_AUTHORITY_MATRIX_SHA256 = (
    "ca99b1fb4f3f1d7af553c61e3fc9c82e815f648052899344e0dbfa89ec5158bc"
)
EXPECTED_P1_METRIC_CATALOG_SHA256 = (
    "24ab6d06ced0b768ff16e4c945e778cc8fd2d3838be3ca30051ec8f8e0d7277d"
)
EXPECTED_METRIC_CODES = ("P1-QA-006",) + tuple(
    f"P1-SNS-{index:03d}" for index in range(5, 22)
)
EXPECTED_PROFILE_ERROR_DOMAINS = (
    "AZIMUTH",
    "CROSS_RANGE",
    "ELEVATION",
    "POSITION_3D",
    "RADIAL_POSITION",
    "RADIAL_VELOCITY",
    "RANGE",
    "VERTICAL_POSITION",
)
EXPECTED_PROFILE_REASON_KEYS = (
    "ASSOCIATION_INVALID",
    "MATCH_STATUS_INVALID",
    "INTERPOLATION_AGE_EXCEEDED",
    "REFERENCE_QUALITY_REJECTED",
    "UNCERTAINTY_COMPONENT_MISSING",
    "UNCERTAINTY_DOMAIN_CAP_EXCEEDED",
    "NO_VALID_MATCHED_SAMPLES",
)
PROFILE_HASH_FIELDS = (
    "profile_id",
    "profile_version",
    "max_gap_us",
    "min_coverage",
    "max_interpolation_age_us",
    "accepted_reference_quality_statuses",
    "max_sigma_by_error_domain",
    "required_uncertainty_components",
    "na_reason_map",
)


class M2MeasurementAlignmentError(RuntimeError):
    """Deterministic fail-closed measurement/reference alignment error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ReferenceMatchQualityProfile:
    profile_id: str
    profile_version: str
    profile_hash: str
    max_gap_us: int
    min_coverage: float
    max_interpolation_age_us: int
    accepted_reference_quality_statuses: tuple[str, ...]
    max_sigma_by_error_domain: MappingProxyType[str, float | None]
    required_uncertainty_components: tuple[str, ...]
    na_reason_map: MappingProxyType[str, str]

    def as_contract(self) -> MappingProxyType[str, object]:
        """Return the exact governed SNS match-quality contract payload."""

        return MappingProxyType(
            {
                "profile_id": self.profile_id,
                "profile_version": self.profile_version,
                "profile_hash": self.profile_hash,
                "max_gap_us": self.max_gap_us,
                "min_coverage": self.min_coverage,
                "max_interpolation_age_us": self.max_interpolation_age_us,
                "accepted_reference_quality_statuses": list(
                    self.accepted_reference_quality_statuses
                ),
                "max_sigma_by_error_domain": dict(self.max_sigma_by_error_domain),
                "required_uncertainty_components": list(
                    self.required_uncertainty_components
                ),
                "na_reason_map": dict(self.na_reason_map),
            }
        )


@dataclass(frozen=True)
class MeasurementAlignmentRow:
    measurement_id: str
    reference_state_id: str
    mission_system_instance_id: str
    target_pair_id: str
    measurement_time_us: int
    reference_time_us: int
    gap_us: int
    match_status: str
    measured_range_m: float
    reference_range_m: float
    measured_az_rad: float
    reference_az_rad: float
    measured_el_rad: float
    reference_el_rad: float
    measured_position_ecef_m: tuple[float, float, float]
    reference_target_position_ecef_m: tuple[float, float, float]
    measured_radial_velocity_mps: float
    reference_range_rate_mps: float
    measured_position_sensor_frame: tuple[float, float, float]
    reference_position_sensor_frame: tuple[float, float, float]
    measured_position_local: tuple[float, float, float]
    reference_position_local: tuple[float, float, float]
    sensor_measurement: MappingProxyType[str, float]
    reference_relative_state: MappingProxyType[str, float]
    residual_unit: str
    error_domain: str
    measurement_error: float
    reference_uncertainty: float
    alignment_uncertainty: float
    sensor_measurement_uncertainty: float
    reference_truth_uncertainty: float
    uncertainty_provenance: MappingProxyType[str, str]


@dataclass(frozen=True)
class M2MeasurementAlignmentProjection:
    fixture_id: str
    fixture_version: str
    session_id: str
    mission_system_instance_id: str
    target_pair_id: str
    input_sha256: str
    source_sha256: str
    reference_truth_logical_hash: str
    mission_system_logical_hash: str
    quality_profile: ReferenceMatchQualityProfile
    rows: tuple[MeasurementAlignmentRow, ...]
    coverage: float
    max_observed_gap_us: int
    status: str
    reason_codes: tuple[str, ...]
    logical_hash: str
    metric_codes: tuple[str, ...] = EXPECTED_METRIC_CODES
    metric_logic_executed: bool = False
    stage_projection_executed: bool = False
    persistence_executed: bool = False
    publication_executed: bool = False


def _load_json(path: Path, *, code: str) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise M2MeasurementAlignmentError(code, path.as_posix()) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M2MeasurementAlignmentError(code, f"{path.as_posix()}: {exc}") from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise M2MeasurementAlignmentError(code, f"{path.as_posix()}: root must be object")
    return cast(dict[str, object], raw)


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_SOURCE_INVALID",
            f"{field} must be string-keyed object",
        )
    return cast(dict[str, object], value)


def _required_str(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_SOURCE_INVALID",
            f"{key} must be non-empty string",
        )
    return value


def _required_int(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_SOURCE_INVALID",
            f"{key} must be integer",
        )
    return value


def _required_number(mapping: dict[str, object], key: str) -> float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_SOURCE_INVALID",
            f"{key} must be numeric",
        )
    result = float(value)
    if not math.isfinite(result):
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_SOURCE_INVALID",
            f"{key} must be finite",
        )
    return result


def _vector3(value: object, *, field: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_SOURCE_INVALID",
            f"{field} must contain three numbers",
        )
    output: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise M2MeasurementAlignmentError(
                "M2_MEASUREMENT_ALIGNMENT_SOURCE_INVALID",
                f"{field} must contain only numbers",
            )
        number = float(item)
        if not math.isfinite(number):
            raise M2MeasurementAlignmentError(
                "M2_MEASUREMENT_ALIGNMENT_SOURCE_INVALID",
                f"{field} must contain only finite numbers",
            )
        output.append(number)
    return cast(tuple[float, float, float], tuple(output))


def _numeric_mapping(value: object, *, field: str) -> MappingProxyType[str, float]:
    raw = _object(value, field=field)
    output: dict[str, float] = {}
    for key, item in raw.items():
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise M2MeasurementAlignmentError(
                "M2_MEASUREMENT_ALIGNMENT_SOURCE_INVALID",
                f"{field}.{key} must be numeric",
            )
        number = float(item)
        if not math.isfinite(number):
            raise M2MeasurementAlignmentError(
                "M2_MEASUREMENT_ALIGNMENT_SOURCE_INVALID",
                f"{field}.{key} must be finite",
            )
        output[key] = number
    return MappingProxyType(dict(sorted(output.items())))


def _string_mapping(value: object, *, field: str) -> MappingProxyType[str, str]:
    raw = _object(value, field=field)
    output: dict[str, str] = {}
    for key, item in raw.items():
        if not isinstance(item, str) or not item:
            raise M2MeasurementAlignmentError(
                "M2_MEASUREMENT_ALIGNMENT_SOURCE_INVALID",
                f"{field}.{key} must be non-empty string",
            )
        output[key] = item
    return MappingProxyType(dict(sorted(output.items())))


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError as exc:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_SOURCE_MISSING",
            path.as_posix(),
        ) from exc


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _input_hash(source_sha256: str) -> str:
    payload = f"{EXPECTED_SOURCE_RELATIVE_PATH}={source_sha256}\n".encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _profile(raw: dict[str, object]) -> ReferenceMatchQualityProfile:
    profile_id = _required_str(raw, "profile_id")
    profile_version = _required_str(raw, "profile_version")
    profile_hash = _required_str(raw, "profile_hash")
    max_gap_us = _required_int(raw, "max_gap_us")
    min_coverage = _required_number(raw, "min_coverage")
    max_interpolation_age_us = _required_int(raw, "max_interpolation_age_us")

    accepted_raw = raw.get("accepted_reference_quality_statuses")
    if (
        not isinstance(accepted_raw, list)
        or not accepted_raw
        or not all(isinstance(item, str) and item for item in accepted_raw)
        or len(set(accepted_raw)) != len(accepted_raw)
    ):
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_QUALITY_PROFILE_INVALID",
            "accepted_reference_quality_statuses must be unique non-empty strings",
        )
    accepted_reference_quality_statuses = cast(tuple[str, ...], tuple(accepted_raw))

    required_raw = raw.get("required_uncertainty_components")
    if (
        not isinstance(required_raw, list)
        or not required_raw
        or not all(isinstance(item, str) and item for item in required_raw)
        or len(set(required_raw)) != len(required_raw)
    ):
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_QUALITY_PROFILE_INVALID",
            "required_uncertainty_components must be unique non-empty strings",
        )
    required_uncertainty_components = cast(tuple[str, ...], tuple(required_raw))

    caps_raw = _object(
        raw.get("max_sigma_by_error_domain"),
        field="quality_profile.max_sigma_by_error_domain",
    )
    if set(caps_raw) != set(EXPECTED_PROFILE_ERROR_DOMAINS):
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_QUALITY_PROFILE_INVALID",
            "max_sigma_by_error_domain keys do not match adopted authority",
        )
    max_sigma_by_error_domain: dict[str, float | None] = {}
    for domain in EXPECTED_PROFILE_ERROR_DOMAINS:
        value = caps_raw[domain]
        if value is None:
            max_sigma_by_error_domain[domain] = None
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0.0
        ):
            raise M2MeasurementAlignmentError(
                "M2_MEASUREMENT_ALIGNMENT_QUALITY_PROFILE_INVALID",
                f"max_sigma_by_error_domain.{domain} must be null or non-negative finite number",
            )
        max_sigma_by_error_domain[domain] = float(value)

    reasons_raw = _object(
        raw.get("na_reason_map"),
        field="quality_profile.na_reason_map",
    )
    if set(reasons_raw) != set(EXPECTED_PROFILE_REASON_KEYS):
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_QUALITY_PROFILE_INVALID",
            "na_reason_map keys do not match adopted authority",
        )
    na_reason_map = {
        key: _required_str(reasons_raw, key)
        for key in EXPECTED_PROFILE_REASON_KEYS
    }

    if (
        max_gap_us < 0
        or max_interpolation_age_us < 0
        or not 0.0 <= min_coverage <= 1.0
    ):
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_QUALITY_PROFILE_INVALID",
            (
                f"max_gap_us={max_gap_us} "
                f"max_interpolation_age_us={max_interpolation_age_us} "
                f"min_coverage={min_coverage}"
            ),
        )
    if (
        profile_id != EXPECTED_REFERENCE_MATCH_QUALITY_PROFILE_ID
        or profile_version != EXPECTED_REFERENCE_MATCH_QUALITY_PROFILE_VERSION
    ):
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_QUALITY_PROFILE_AUTHORITY_MISMATCH",
            f"profile={profile_id}@{profile_version}",
        )

    expected_hash = _canonical_hash({key: raw[key] for key in PROFILE_HASH_FIELDS})
    if (
        profile_hash != expected_hash
        or profile_hash != EXPECTED_REFERENCE_MATCH_QUALITY_PROFILE_SHA256
    ):
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_QUALITY_PROFILE_HASH_MISMATCH",
            f"expected={profile_hash} actual={expected_hash}",
        )
    return ReferenceMatchQualityProfile(
        profile_id=profile_id,
        profile_version=profile_version,
        profile_hash=profile_hash,
        max_gap_us=max_gap_us,
        min_coverage=min_coverage,
        max_interpolation_age_us=max_interpolation_age_us,
        accepted_reference_quality_statuses=accepted_reference_quality_statuses,
        max_sigma_by_error_domain=MappingProxyType(
            dict(sorted(max_sigma_by_error_domain.items()))
        ),
        required_uncertainty_components=required_uncertainty_components,
        na_reason_map=MappingProxyType(dict(sorted(na_reason_map.items()))),
    )


def _logical_hash(
    *,
    fixture_id: str,
    session_id: str,
    mission_system_instance_id: str,
    target_pair_id: str,
    reference_truth_logical_hash: str,
    mission_system_logical_hash: str,
    quality_profile: ReferenceMatchQualityProfile,
    rows: tuple[MeasurementAlignmentRow, ...],
    coverage: float,
    max_observed_gap_us: int,
    status: str,
    reason_codes: tuple[str, ...],
) -> str:
    return _canonical_hash(
        {
            "fixture_id": fixture_id,
            "session_id": session_id,
            "mission_system_instance_id": mission_system_instance_id,
            "target_pair_id": target_pair_id,
            "reference_truth_logical_hash": reference_truth_logical_hash,
            "mission_system_logical_hash": mission_system_logical_hash,
            "quality_profile": dict(quality_profile.as_contract()),
            "coverage": coverage,
            "max_observed_gap_us": max_observed_gap_us,
            "status": status,
            "reason_codes": reason_codes,
            "rows": [
                {
                    "measurement_id": row.measurement_id,
                    "reference_state_id": row.reference_state_id,
                    "measurement_time_us": row.measurement_time_us,
                    "reference_time_us": row.reference_time_us,
                    "gap_us": row.gap_us,
                    "match_status": row.match_status,
                    "measured_range_m": row.measured_range_m,
                    "reference_range_m": row.reference_range_m,
                    "measured_az_rad": row.measured_az_rad,
                    "reference_az_rad": row.reference_az_rad,
                    "measured_el_rad": row.measured_el_rad,
                    "reference_el_rad": row.reference_el_rad,
                    "measured_position_ecef_m": row.measured_position_ecef_m,
                    "reference_target_position_ecef_m": row.reference_target_position_ecef_m,
                    "measured_radial_velocity_mps": row.measured_radial_velocity_mps,
                    "reference_range_rate_mps": row.reference_range_rate_mps,
                    "measured_position_sensor_frame": row.measured_position_sensor_frame,
                    "reference_position_sensor_frame": row.reference_position_sensor_frame,
                    "measured_position_local": row.measured_position_local,
                    "reference_position_local": row.reference_position_local,
                    "sensor_measurement": dict(row.sensor_measurement),
                    "reference_relative_state": dict(row.reference_relative_state),
                    "residual_unit": row.residual_unit,
                    "error_domain": row.error_domain,
                    "measurement_error": row.measurement_error,
                    "reference_uncertainty": row.reference_uncertainty,
                    "alignment_uncertainty": row.alignment_uncertainty,
                    "sensor_measurement_uncertainty": row.sensor_measurement_uncertainty,
                    "reference_truth_uncertainty": row.reference_truth_uncertainty,
                    "uncertainty_provenance": dict(row.uncertainty_provenance),
                }
                for row in rows
            ],
        }
    )


def load_m2_measurement_alignment(bundle: Path) -> M2MeasurementAlignmentProjection:
    """Load one governed M2 measurement/reference match fixture."""

    manifest = _load_json(
        bundle / "manifest.json",
        code="M2_MEASUREMENT_ALIGNMENT_MANIFEST_INVALID",
    )
    fixture_id = manifest.get("fixture_id")
    if (
        manifest.get("schema") != EXPECTED_MANIFEST_SCHEMA
        or fixture_id not in EXPECTED_FIXTURE_IDS
        or bundle.name != fixture_id
    ):
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_FIXTURE_NOT_GOVERNED",
            f"manifest={fixture_id!r} directory={bundle.name!r}",
        )
    if manifest.get("fixture_version") != EXPECTED_FIXTURE_VERSION:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_VERSION_UNSUPPORTED",
            repr(manifest.get("fixture_version")),
        )
    if manifest.get("data_classification") != EXPECTED_CLASSIFICATION:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_CLASSIFICATION_FORBIDDEN",
            repr(manifest.get("data_classification")),
        )
    if manifest.get("input_hash_algorithm") != EXPECTED_HASH_ALGORITHM:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_HASH_ALGORITHM_MISMATCH",
            repr(manifest.get("input_hash_algorithm")),
        )
    if manifest.get("input_hash_basis") != [EXPECTED_SOURCE_RELATIVE_PATH]:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_HASH_BASIS_MISMATCH",
            repr(manifest.get("input_hash_basis")),
        )

    authority = _object(manifest.get("authority_refs"), field="authority_refs")
    expected_authority: dict[str, object] = {
        "core_baseline": EXPECTED_CORE_BASELINE,
        "metric_codes": list(EXPECTED_METRIC_CODES),
        "metric_input_authority_matrix_sha256": EXPECTED_METRIC_INPUT_AUTHORITY_MATRIX_SHA256,
        "mission_system_measurement_authority": EXPECTED_MEASUREMENT_AUTHORITY,
        "p1_metric_catalog_sha256": EXPECTED_P1_METRIC_CATALOG_SHA256,
        "reference_match_quality_contract": EXPECTED_REFERENCE_MATCH_QUALITY_CONTRACT,
        "reference_navigation_authority": EXPECTED_REFERENCE_AUTHORITY,
        "reference_relative_state_contract": EXPECTED_REFERENCE_RELATIVE_STATE_CONTRACT,
    }
    if authority != expected_authority:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_AUTHORITY_MISMATCH",
            repr(authority),
        )

    files = _object(manifest.get("files"), field="files")
    source_ref = _object(files.get("source"), field="files.source")
    if source_ref.get("path") != EXPECTED_SOURCE_RELATIVE_PATH:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_SOURCE_PATH_MISMATCH",
            repr(source_ref.get("path")),
        )
    source_path = bundle / EXPECTED_SOURCE_RELATIVE_PATH
    source_sha256 = _sha256_file(source_path)
    if source_ref.get("sha256") != source_sha256:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_SOURCE_HASH_MISMATCH",
            f"expected={source_ref.get('sha256')} actual={source_sha256}",
        )
    input_sha256 = _input_hash(source_sha256)
    if manifest.get("input_sha256") != input_sha256:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_INPUT_HASH_MISMATCH",
            f"expected={manifest.get('input_sha256')} actual={input_sha256}",
        )

    source = _load_json(source_path, code="M2_MEASUREMENT_ALIGNMENT_SOURCE_INVALID")
    if source.get("schema") != EXPECTED_SOURCE_SCHEMA or source.get("fixture_id") != fixture_id:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_SOURCE_SCHEMA_MISMATCH",
            repr(source.get("schema")),
        )
    if source.get("data_classification") != EXPECTED_CLASSIFICATION:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_CLASSIFICATION_FORBIDDEN",
            repr(source.get("data_classification")),
        )

    fixture_root = bundle.parent
    reference_fixture = _required_str(source, "reference_fixture_id")
    mission_fixture = _required_str(source, "mission_system_fixture_id")
    if reference_fixture != EXPECTED_REFERENCE_FIXTURE or mission_fixture != EXPECTED_MISSION_SYSTEM_FIXTURE:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_UPSTREAM_FIXTURE_MISMATCH",
            f"reference={reference_fixture} mission={mission_fixture}",
        )
    reference = load_m2_reference_truth(fixture_root / reference_fixture)
    mission = load_m2_mission_system(fixture_root / mission_fixture)

    session_id = _required_str(source, "session_id")
    mission_system_instance_id = _required_str(source, "mission_system_instance_id")
    target_pair_id = _required_str(source, "target_pair_id")
    expected_pair = f"{reference.own_identity.aircraft_id}:{reference.target_identity.aircraft_id}"
    if session_id != reference.session_id:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_SESSION_MISMATCH",
            f"source={session_id} reference={reference.session_id}",
        )
    if mission_system_instance_id != mission.instance.mission_system_instance_id:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_MISSION_SYSTEM_MISMATCH",
            f"source={mission_system_instance_id} mission={mission.instance.mission_system_instance_id}",
        )
    if target_pair_id != expected_pair:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_TARGET_PAIR_MISMATCH",
            f"source={target_pair_id} expected={expected_pair}",
        )

    quality_profile = _profile(_object(source.get("quality_profile"), field="quality_profile"))
    raw_rows = source.get("records")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise M2MeasurementAlignmentError(
            "M2_MEASUREMENT_ALIGNMENT_SOURCE_INVALID",
            "records must be non-empty list",
        )

    rows: list[MeasurementAlignmentRow] = []
    valid_count = 0
    previous_measurement_time: int | None = None
    for index, raw_row in enumerate(raw_rows):
        row = _object(raw_row, field=f"records[{index}]")
        measurement_time_us = _required_int(row, "measurement_time_us")
        reference_time_us = _required_int(row, "reference_time_us")
        if previous_measurement_time is not None and measurement_time_us <= previous_measurement_time:
            raise M2MeasurementAlignmentError(
                "M2_MEASUREMENT_ALIGNMENT_TIME_ORDER_INVALID",
                f"index={index} value={measurement_time_us}",
            )
        previous_measurement_time = measurement_time_us
        valid = row.get("valid")
        if not isinstance(valid, bool):
            raise M2MeasurementAlignmentError(
                "M2_MEASUREMENT_ALIGNMENT_SOURCE_INVALID",
                f"records[{index}].valid must be bool",
            )
        gap_us = abs(measurement_time_us - reference_time_us)
        accepted = valid and gap_us <= quality_profile.max_gap_us
        if accepted:
            valid_count += 1

        measured_range_m = _required_number(row, "measured_range_m")
        reference_range_m = _required_number(row, "reference_range_m")
        measurement_error = _required_number(row, "measurement_error")
        if not math.isclose(
            measurement_error,
            measured_range_m - reference_range_m,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise M2MeasurementAlignmentError(
                "M2_MEASUREMENT_ALIGNMENT_RESIDUAL_INCONSISTENT",
                f"index={index}",
            )

        rows.append(
            MeasurementAlignmentRow(
                measurement_id=_required_str(row, "measurement_id"),
                reference_state_id=_required_str(row, "reference_state_id"),
                mission_system_instance_id=mission_system_instance_id,
                target_pair_id=target_pair_id,
                measurement_time_us=measurement_time_us,
                reference_time_us=reference_time_us,
                gap_us=gap_us,
                match_status="MATCHED" if accepted else "REJECTED_QUALITY",
                measured_range_m=measured_range_m,
                reference_range_m=reference_range_m,
                measured_az_rad=_required_number(row, "measured_az_rad"),
                reference_az_rad=_required_number(row, "reference_az_rad"),
                measured_el_rad=_required_number(row, "measured_el_rad"),
                reference_el_rad=_required_number(row, "reference_el_rad"),
                measured_position_ecef_m=_vector3(
                    row.get("measured_position_ecef_m"),
                    field=f"records[{index}].measured_position_ecef_m",
                ),
                reference_target_position_ecef_m=_vector3(
                    row.get("reference_target_position_ecef_m"),
                    field=f"records[{index}].reference_target_position_ecef_m",
                ),
                measured_radial_velocity_mps=_required_number(
                    row,
                    "measured_radial_velocity_mps",
                ),
                reference_range_rate_mps=_required_number(
                    row,
                    "reference_range_rate_mps",
                ),
                measured_position_sensor_frame=_vector3(
                    row.get("measured_position_sensor_frame"),
                    field=f"records[{index}].measured_position_sensor_frame",
                ),
                reference_position_sensor_frame=_vector3(
                    row.get("reference_position_sensor_frame"),
                    field=f"records[{index}].reference_position_sensor_frame",
                ),
                measured_position_local=_vector3(
                    row.get("measured_position_local"),
                    field=f"records[{index}].measured_position_local",
                ),
                reference_position_local=_vector3(
                    row.get("reference_position_local"),
                    field=f"records[{index}].reference_position_local",
                ),
                sensor_measurement=_numeric_mapping(
                    row.get("sensor_measurement"),
                    field=f"records[{index}].sensor_measurement",
                ),
                reference_relative_state=_numeric_mapping(
                    row.get("reference_relative_state"),
                    field=f"records[{index}].reference_relative_state",
                ),
                residual_unit=_required_str(row, "residual_unit"),
                error_domain=_required_str(row, "error_domain"),
                measurement_error=measurement_error,
                reference_uncertainty=_required_number(row, "reference_uncertainty"),
                alignment_uncertainty=_required_number(row, "alignment_uncertainty"),
                sensor_measurement_uncertainty=_required_number(
                    row,
                    "sensor_measurement_uncertainty",
                ),
                reference_truth_uncertainty=_required_number(
                    row,
                    "reference_truth_uncertainty",
                ),
                uncertainty_provenance=_string_mapping(
                    row.get("uncertainty_provenance"),
                    field=f"records[{index}].uncertainty_provenance",
                ),
            )
        )

    projected_rows = tuple(rows)
    coverage = valid_count / len(projected_rows)
    max_observed_gap_us = max(row.gap_us for row in projected_rows)
    reasons: list[str] = []
    if max_observed_gap_us > quality_profile.max_gap_us:
        reasons.append("MAX_GAP_EXCEEDED")
    if coverage < quality_profile.min_coverage:
        reasons.append("MIN_COVERAGE_NOT_MET")
    reason_codes = tuple(reasons)
    status = "READY" if not reason_codes else "INSUFFICIENT"

    logical_hash = _logical_hash(
        fixture_id=fixture_id,
        session_id=session_id,
        mission_system_instance_id=mission_system_instance_id,
        target_pair_id=target_pair_id,
        reference_truth_logical_hash=reference.logical_hash,
        mission_system_logical_hash=mission.logical_hash,
        quality_profile=quality_profile,
        rows=projected_rows,
        coverage=coverage,
        max_observed_gap_us=max_observed_gap_us,
        status=status,
        reason_codes=reason_codes,
    )
    return M2MeasurementAlignmentProjection(
        fixture_id=fixture_id,
        fixture_version=EXPECTED_FIXTURE_VERSION,
        session_id=session_id,
        mission_system_instance_id=mission_system_instance_id,
        target_pair_id=target_pair_id,
        input_sha256=input_sha256,
        source_sha256=source_sha256,
        reference_truth_logical_hash=reference.logical_hash,
        mission_system_logical_hash=mission.logical_hash,
        quality_profile=quality_profile,
        rows=projected_rows,
        coverage=coverage,
        max_observed_gap_us=max_observed_gap_us,
        status=status,
        reason_codes=reason_codes,
        logical_hash=logical_hash,
    )
