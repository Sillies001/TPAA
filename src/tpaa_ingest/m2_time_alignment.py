"""M2-DATA-002 sensor/INS time-alignment input projection.

The adapter validates controlled synthetic fixtures for the frozen P1-QA-003,
P1-QA-004, P1-QA-005, P1-QA-007 and P1-QA-008 input contracts. It preserves
time-transform, effective-time, interpolation and uncertainty provenance only.
It does not execute Metric logic, Stage projection, persistence or publication.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

EXPECTED_MANIFEST_SCHEMA = "TPAA_M2_TIME_ALIGNMENT_FIXTURE_V1"
EXPECTED_SOURCE_SCHEMA = "TPAA_M2_TIME_ALIGNMENT_SOURCE_V1"
EXPECTED_CLASSIFICATION = "SYNTHETIC"
EXPECTED_VERSION = "1.0.0"
EXPECTED_SOURCE_PATH = "source/time-alignment.json"
EXPECTED_CORE_BASELINE = "CB-1.4.0"
EXPECTED_CANONICAL_AUTHORITY = "CANONICAL_REFERENCE_NAVIGATION_V1"
EXPECTED_PROFILE_AUTHORITY = "EVALUATION_PROFILE_V1"
EXPECTED_TIME_TRANSFORM_CONTRACT = "CONTRACT_TIME_TRANSFORM_V1"
EXPECTED_UNCERTAINTY_CONTRACT = "CONTRACT_NAV_UNCERTAINTY_REPRESENTATION_V1"
EXPECTED_METRIC_CODES = (
    "P1-QA-003",
    "P1-QA-004",
    "P1-QA-005",
    "P1-QA-007",
    "P1-QA-008",
)
EXPECTED_METRIC_INPUT_AUTHORITY_MATRIX_SHA256 = (
    "ca99b1fb4f3f1d7af553c61e3fc9c82e815f648052899344e0dbfa89ec5158bc"
)
EXPECTED_P1_METRIC_CATALOG_SHA256 = (
    "24ab6d06ced0b768ff16e4c945e778cc8fd2d3838be3ca30051ec8f8e0d7277d"
)


class M2TimeAlignmentError(RuntimeError):
    """Deterministic fail-closed error for M2 time-alignment inputs."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ClockAlignmentSample:
    sensor_timestamp_mapped_to_session_time_us: int
    aligned_session_time_us: int


@dataclass(frozen=True)
class ClockSegment:
    segment_id: str
    time_transform_id: str
    sensor_system_instance_id: str
    records: tuple[ClockAlignmentSample, ...]


@dataclass(frozen=True)
class LatencyInput:
    sensor_system_instance_id: str
    sensor_measurement_effective_time_us: int
    referenced_ownship_state_effective_time_us: int


@dataclass(frozen=True)
class InterpolationInput:
    target_pair_id: str
    measurement_time_us: int
    left_truth_time_us: int
    right_truth_time_us: int


@dataclass(frozen=True)
class NavTimeUncertaintyInput:
    reference_name: str
    representation: str
    bound_us: int
    provenance_ref: str


@dataclass(frozen=True)
class M2TimeAlignmentProjection:
    fixture_id: str
    fixture_version: str
    session_id: str
    session_time_basis: str
    profile_id: str
    max_gap_us: int
    source_sha256: str
    clock_segments: tuple[ClockSegment, ...]
    latency_records: tuple[LatencyInput, ...]
    interpolation_records: tuple[InterpolationInput, ...]
    uncertainty_records: tuple[NavTimeUncertaintyInput, ...]
    ownship_clock_transform_residual_sigma_us: int
    target_clock_transform_residual_sigma_us: int
    logical_hash: str
    metric_logic_executed: bool = False
    stage_projection_executed: bool = False
    persistence_executed: bool = False


def _load_json(path: Path, *, code: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise M2TimeAlignmentError(code, str(exc)) from exc
    if not isinstance(payload, dict):
        raise M2TimeAlignmentError(code, "top-level JSON value must be object")
    return cast(dict[str, object], payload)


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise M2TimeAlignmentError("M2_TIME_ALIGNMENT_SOURCE_INVALID", f"{field} must be object")
    return cast(dict[str, object], value)


def _list(value: object, *, field: str) -> list[object]:
    if not isinstance(value, list):
        raise M2TimeAlignmentError("M2_TIME_ALIGNMENT_SOURCE_INVALID", f"{field} must be list")
    return cast(list[object], value)


def _str(value: object, *, field: str, unresolved_code: str | None = None) -> str:
    if not isinstance(value, str) or not value:
        code = unresolved_code or "M2_TIME_ALIGNMENT_SOURCE_INVALID"
        raise M2TimeAlignmentError(code, f"{field} must be non-empty string")
    return value


def _int(value: object, *, field: str, unresolved_code: str | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        code = unresolved_code or "M2_TIME_ALIGNMENT_SOURCE_INVALID"
        raise M2TimeAlignmentError(code, f"{field} must be integer")
    return value


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise M2TimeAlignmentError("M2_TIME_ALIGNMENT_SOURCE_MISSING", str(exc)) from exc


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_manifest(bundle: Path) -> tuple[str, dict[str, object]]:
    manifest = _load_json(
        bundle / "manifest.json",
        code="M2_TIME_ALIGNMENT_MANIFEST_INVALID",
    )
    if manifest.get("schema") != EXPECTED_MANIFEST_SCHEMA:
        raise M2TimeAlignmentError(
            "M2_TIME_ALIGNMENT_MANIFEST_SCHEMA_MISMATCH",
            repr(manifest.get("schema")),
        )
    fixture_id = _str(manifest.get("fixture_id"), field="fixture_id")
    if fixture_id != bundle.name:
        raise M2TimeAlignmentError(
            "M2_TIME_ALIGNMENT_FIXTURE_NOT_GOVERNED",
            f"manifest={fixture_id!r} directory={bundle.name!r}",
        )
    if manifest.get("fixture_version") != EXPECTED_VERSION:
        raise M2TimeAlignmentError(
            "M2_TIME_ALIGNMENT_VERSION_UNSUPPORTED",
            repr(manifest.get("fixture_version")),
        )
    if manifest.get("data_classification") != EXPECTED_CLASSIFICATION:
        raise M2TimeAlignmentError(
            "M2_TIME_ALIGNMENT_CLASSIFICATION_FORBIDDEN",
            repr(manifest.get("data_classification")),
        )
    if manifest.get("input_hash_algorithm") != "SHA256_FILE_V1":
        raise M2TimeAlignmentError(
            "M2_TIME_ALIGNMENT_HASH_ALGORITHM_MISMATCH",
            repr(manifest.get("input_hash_algorithm")),
        )
    if manifest.get("input_hash_basis") != [EXPECTED_SOURCE_PATH]:
        raise M2TimeAlignmentError(
            "M2_TIME_ALIGNMENT_HASH_BASIS_MISMATCH",
            repr(manifest.get("input_hash_basis")),
        )

    authority = _object(manifest.get("authority_refs"), field="authority_refs")
    expected_authority: dict[str, object] = {
        "canonical_reference_navigation": EXPECTED_CANONICAL_AUTHORITY,
        "core_baseline": EXPECTED_CORE_BASELINE,
        "evaluation_profile": EXPECTED_PROFILE_AUTHORITY,
        "metric_codes": list(EXPECTED_METRIC_CODES),
        "metric_input_authority_matrix_sha256": (
            EXPECTED_METRIC_INPUT_AUTHORITY_MATRIX_SHA256
        ),
        "nav_uncertainty_contract": EXPECTED_UNCERTAINTY_CONTRACT,
        "p1_metric_catalog_sha256": EXPECTED_P1_METRIC_CATALOG_SHA256,
        "time_transform_contract": EXPECTED_TIME_TRANSFORM_CONTRACT,
    }
    if authority != expected_authority:
        raise M2TimeAlignmentError(
            "M2_TIME_ALIGNMENT_AUTHORITY_MISMATCH",
            repr(authority),
        )

    files = _object(manifest.get("files"), field="files")
    source_ref = _object(files.get("source"), field="files.source")
    if source_ref.get("path") != EXPECTED_SOURCE_PATH:
        raise M2TimeAlignmentError(
            "M2_TIME_ALIGNMENT_SOURCE_PATH_MISMATCH",
            repr(source_ref.get("path")),
        )
    source_path = bundle / EXPECTED_SOURCE_PATH
    actual_sha = _sha256(source_path)
    if source_ref.get("sha256") != actual_sha or manifest.get("input_sha256") != actual_sha:
        raise M2TimeAlignmentError(
            "M2_TIME_ALIGNMENT_SOURCE_HASH_MISMATCH",
            f"manifest={source_ref.get('sha256')} input={manifest.get('input_sha256')} "
            f"actual={actual_sha}",
        )
    return actual_sha, manifest


def load_m2_time_alignment(bundle: Path) -> M2TimeAlignmentProjection:
    """Validate and project one governed M2 time-alignment fixture."""

    source_sha256, manifest = _validate_manifest(bundle)
    source = _load_json(
        bundle / EXPECTED_SOURCE_PATH,
        code="M2_TIME_ALIGNMENT_SOURCE_INVALID",
    )
    if source.get("schema") != EXPECTED_SOURCE_SCHEMA:
        raise M2TimeAlignmentError(
            "M2_TIME_ALIGNMENT_SOURCE_SCHEMA_MISMATCH",
            repr(source.get("schema")),
        )
    fixture_id = _str(source.get("fixture_id"), field="fixture_id")
    if fixture_id != manifest.get("fixture_id"):
        raise M2TimeAlignmentError(
            "M2_TIME_ALIGNMENT_SOURCE_FIXTURE_MISMATCH",
            repr(fixture_id),
        )
    if source.get("data_classification") != EXPECTED_CLASSIFICATION:
        raise M2TimeAlignmentError(
            "M2_TIME_ALIGNMENT_CLASSIFICATION_FORBIDDEN",
            repr(source.get("data_classification")),
        )

    session = _object(source.get("session"), field="session")
    session_id = _str(session.get("session_id"), field="session.session_id")
    session_time_basis = _str(
        session.get("session_time_basis"),
        field="session.session_time_basis",
    )

    profile = _object(source.get("profile"), field="profile")
    profile_id = _str(profile.get("profile_id"), field="profile.profile_id")
    max_gap_us = _int(profile.get("max_gap_us"), field="profile.max_gap_us")
    if max_gap_us <= 0:
        raise M2TimeAlignmentError(
            "M2_TIME_ALIGNMENT_PROFILE_INVALID",
            f"max_gap_us={max_gap_us}",
        )

    segments: list[ClockSegment] = []
    for segment_index, raw_segment in enumerate(
        _list(source.get("clock_segments"), field="clock_segments")
    ):
        segment = _object(raw_segment, field=f"clock_segments[{segment_index}]")
        time_transform_id = _str(
            segment.get("time_transform_id"),
            field=f"clock_segments[{segment_index}].time_transform_id",
            unresolved_code="M2_TIME_ALIGNMENT_TIME_TRANSFORM_UNRESOLVED",
        )
        records: list[ClockAlignmentSample] = []
        for record_index, raw_record in enumerate(
            _list(segment.get("records"), field=f"clock_segments[{segment_index}].records")
        ):
            record = _object(
                raw_record,
                field=f"clock_segments[{segment_index}].records[{record_index}]",
            )
            records.append(
                ClockAlignmentSample(
                    sensor_timestamp_mapped_to_session_time_us=_int(
                        record.get("sensor_timestamp_mapped_to_session_time_us"),
                        field="sensor_timestamp_mapped_to_session_time_us",
                        unresolved_code="M2_TIME_ALIGNMENT_TIME_TRANSFORM_UNRESOLVED",
                    ),
                    aligned_session_time_us=_int(
                        record.get("aligned_session_time_us"),
                        field="aligned_session_time_us",
                        unresolved_code="M2_TIME_ALIGNMENT_TIME_TRANSFORM_UNRESOLVED",
                    ),
                )
            )
        if not records:
            raise M2TimeAlignmentError(
                "M2_TIME_ALIGNMENT_SOURCE_INVALID",
                f"clock_segments[{segment_index}].records must not be empty",
            )
        segments.append(
            ClockSegment(
                segment_id=_str(
                    segment.get("segment_id"),
                    field=f"clock_segments[{segment_index}].segment_id",
                ),
                time_transform_id=time_transform_id,
                sensor_system_instance_id=_str(
                    segment.get("sensor_system_instance_id"),
                    field=f"clock_segments[{segment_index}].sensor_system_instance_id",
                ),
                records=tuple(records),
            )
        )
    if not segments:
        raise M2TimeAlignmentError(
            "M2_TIME_ALIGNMENT_SOURCE_INVALID",
            "clock_segments must not be empty",
        )

    latency_records: list[LatencyInput] = []
    for index, raw_record in enumerate(
        _list(source.get("latency_records"), field="latency_records")
    ):
        record = _object(raw_record, field=f"latency_records[{index}]")
        latency_records.append(
            LatencyInput(
                sensor_system_instance_id=_str(
                    record.get("sensor_system_instance_id"),
                    field=f"latency_records[{index}].sensor_system_instance_id",
                ),
                sensor_measurement_effective_time_us=_int(
                    record.get("sensor_measurement_effective_time_us"),
                    field=f"latency_records[{index}].sensor_measurement_effective_time_us",
                    unresolved_code="M2_TIME_ALIGNMENT_EFFECTIVE_TIME_UNRESOLVED",
                ),
                referenced_ownship_state_effective_time_us=_int(
                    record.get("referenced_ownship_state_effective_time_us"),
                    field=(
                        f"latency_records[{index}]."
                        "referenced_ownship_state_effective_time_us"
                    ),
                    unresolved_code="M2_TIME_ALIGNMENT_EFFECTIVE_TIME_UNRESOLVED",
                ),
            )
        )

    interpolation_records: list[InterpolationInput] = []
    for index, raw_record in enumerate(
        _list(source.get("interpolation_records"), field="interpolation_records")
    ):
        record = _object(raw_record, field=f"interpolation_records[{index}]")
        measurement = _int(
            record.get("measurement_time_us"),
            field=f"interpolation_records[{index}].measurement_time_us",
            unresolved_code="M2_TIME_ALIGNMENT_BRACKET_UNRESOLVED",
        )
        left = _int(
            record.get("left_truth_time_us"),
            field=f"interpolation_records[{index}].left_truth_time_us",
            unresolved_code="M2_TIME_ALIGNMENT_BRACKET_UNRESOLVED",
        )
        right = _int(
            record.get("right_truth_time_us"),
            field=f"interpolation_records[{index}].right_truth_time_us",
            unresolved_code="M2_TIME_ALIGNMENT_BRACKET_UNRESOLVED",
        )
        if not left <= measurement <= right:
            raise M2TimeAlignmentError(
                "M2_TIME_ALIGNMENT_BRACKET_INVALID",
                f"left={left} measurement={measurement} right={right}",
            )
        interpolation_records.append(
            InterpolationInput(
                target_pair_id=_str(
                    record.get("target_pair_id"),
                    field=f"interpolation_records[{index}].target_pair_id",
                ),
                measurement_time_us=measurement,
                left_truth_time_us=left,
                right_truth_time_us=right,
            )
        )

    uncertainty_raw = _object(
        source.get("uncertainty_records"),
        field="uncertainty_records",
    )
    uncertainty_records: list[NavTimeUncertaintyInput] = []
    for ref_name in (
        "ownship_nav_time_uncertainty_ref",
        "target_nav_time_uncertainty_ref",
    ):
        record = _object(uncertainty_raw.get(ref_name), field=ref_name)
        representation = _str(record.get("representation"), field=f"{ref_name}.representation")
        if representation != "TWO_SIDED_HARD_BOUND":
            raise M2TimeAlignmentError(
                "M2_TIME_ALIGNMENT_UNCERTAINTY_REPRESENTATION_UNSUPPORTED",
                f"{ref_name}={representation}",
            )
        bound_us = _int(
            record.get("bound_us"),
            field=f"{ref_name}.bound_us",
            unresolved_code="M2_TIME_ALIGNMENT_UNCERTAINTY_UNRESOLVED",
        )
        if bound_us <= 0:
            raise M2TimeAlignmentError(
                "M2_TIME_ALIGNMENT_UNCERTAINTY_INVALID",
                f"{ref_name}.bound_us={bound_us}",
            )
        uncertainty_records.append(
            NavTimeUncertaintyInput(
                reference_name=ref_name,
                representation=representation,
                bound_us=bound_us,
                provenance_ref=_str(
                    record.get("provenance_ref"),
                    field=f"{ref_name}.provenance_ref",
                    unresolved_code="M2_TIME_ALIGNMENT_UNCERTAINTY_UNRESOLVED",
                ),
            )
        )

    residuals = _object(source.get("transform_residuals"), field="transform_residuals")
    own_residual = _int(
        residuals.get("ownship_clock_transform_residual_sigma_us"),
        field="ownship_clock_transform_residual_sigma_us",
        unresolved_code="M2_TIME_ALIGNMENT_UNCERTAINTY_UNRESOLVED",
    )
    target_residual = _int(
        residuals.get("target_clock_transform_residual_sigma_us"),
        field="target_clock_transform_residual_sigma_us",
        unresolved_code="M2_TIME_ALIGNMENT_UNCERTAINTY_UNRESOLVED",
    )
    if own_residual < 0 or target_residual < 0:
        raise M2TimeAlignmentError(
            "M2_TIME_ALIGNMENT_UNCERTAINTY_INVALID",
            f"residuals={own_residual},{target_residual}",
        )

    logical_payload: dict[str, object] = {
        "fixture_id": fixture_id,
        "session_id": session_id,
        "session_time_basis": session_time_basis,
        "profile_id": profile_id,
        "max_gap_us": max_gap_us,
        "clock_segments": [
            {
                "segment_id": item.segment_id,
                "time_transform_id": item.time_transform_id,
                "sensor_system_instance_id": item.sensor_system_instance_id,
                "records": [
                    {
                        "sensor_timestamp_mapped_to_session_time_us": (
                            row.sensor_timestamp_mapped_to_session_time_us
                        ),
                        "aligned_session_time_us": row.aligned_session_time_us,
                    }
                    for row in item.records
                ],
            }
            for item in segments
        ],
        "latency_records": [record.__dict__ for record in latency_records],
        "interpolation_records": [record.__dict__ for record in interpolation_records],
        "uncertainty_records": [record.__dict__ for record in uncertainty_records],
        "ownship_clock_transform_residual_sigma_us": own_residual,
        "target_clock_transform_residual_sigma_us": target_residual,
    }
    return M2TimeAlignmentProjection(
        fixture_id=fixture_id,
        fixture_version=EXPECTED_VERSION,
        session_id=session_id,
        session_time_basis=session_time_basis,
        profile_id=profile_id,
        max_gap_us=max_gap_us,
        source_sha256=source_sha256,
        clock_segments=tuple(segments),
        latency_records=tuple(latency_records),
        interpolation_records=tuple(interpolation_records),
        uncertainty_records=tuple(uncertainty_records),
        ownship_clock_transform_residual_sigma_us=own_residual,
        target_clock_transform_residual_sigma_us=target_residual,
        logical_hash=_canonical_hash(logical_payload),
    )
