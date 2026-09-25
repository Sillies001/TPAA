"""M2-DATA-001 reference-relative truth input projection.

This adapter is intentionally limited to the frozen P1-QA-001/P1-QA-002 input
contract. It validates one controlled synthetic fixture, maps its source clock
through the fixture's explicit CONTRACT_TIME_TRANSFORM_V1 projection, and
preserves identity/frame/uncertainty provenance. It does not compute Metrics,
Stage products, database rows, or publication artifacts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

EXPECTED_FIXTURE_ID = "RT_M2_NOMINAL_V1"
EXPECTED_FIXTURE_VERSION = "1.0.0"
EXPECTED_MANIFEST_SCHEMA = "TPAA_M2_REFERENCE_TRUTH_FIXTURE_V1"
EXPECTED_SOURCE_SCHEMA = "TPAA_M2_REFERENCE_TRUTH_SOURCE_V1"
EXPECTED_CLASSIFICATION = "SYNTHETIC"
EXPECTED_HASH_ALGORITHM = "SHA256_PATH_SHA256_V1"
EXPECTED_SOURCE_RELATIVE_PATH = "source/reference-truth.json"
EXPECTED_CORE_BASELINE = "CB-1.4.0"
EXPECTED_CANONICAL_AUTHORITY = "CANONICAL_REFERENCE_NAVIGATION_V1"
EXPECTED_TIME_TRANSFORM_CONTRACT = "CONTRACT_TIME_TRANSFORM_V1"
EXPECTED_UNCERTAINTY_CONTRACT = "CONTRACT_NAV_UNCERTAINTY_REPRESENTATION_V1"
EXPECTED_METRIC_CODES = ("P1-QA-001", "P1-QA-002")
EXPECTED_METRIC_INPUT_AUTHORITY_MATRIX_SHA256 = (
    "ca99b1fb4f3f1d7af553c61e3fc9c82e815f648052899344e0dbfa89ec5158bc"
)
EXPECTED_P1_METRIC_CATALOG_SHA256 = (
    "24ab6d06ced0b768ff16e4c945e778cc8fd2d3838be3ca30051ec8f8e0d7277d"
)


class M2ReferenceTruthError(RuntimeError):
    """Deterministic fail-closed M2 reference-truth adapter error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ReferenceIdentity:
    aircraft_id: str
    identity_ref: str
    source_entity_key: str


@dataclass(frozen=True)
class ReferenceFrameProvenance:
    position_frame: str
    velocity_frame: str
    own_attitude_frame_ref: str
    sensor_boresight_frame_ref: str | None


@dataclass(frozen=True)
class ReferenceTruthRow:
    source_time_us: int
    session_time_us: int
    own_position_ecef_m: tuple[float, float, float]
    target_position_ecef_m: tuple[float, float, float]
    own_velocity_ecef_mps: tuple[float, float, float]
    target_velocity_ecef_mps: tuple[float, float, float]
    own_attitude_quat: tuple[float, float, float, float]
    sensor_boresight_quat: tuple[float, float, float, float] | None
    relative_state_jacobian: tuple[tuple[float, ...], ...]
    uncertainty_refs: MappingProxyType[str, str]


@dataclass(frozen=True)
class M2ReferenceTruthProjection:
    fixture_id: str
    fixture_version: str
    session_id: str
    source_time_basis: str
    input_sha256: str
    source_sha256: str
    time_transform_id: str
    time_transform_hash: str
    own_identity: ReferenceIdentity
    target_identity: ReferenceIdentity
    frame_provenance: ReferenceFrameProvenance
    uncertainty_records: MappingProxyType[str, object]
    rows: tuple[ReferenceTruthRow, ...]
    logical_hash: str
    metric_logic_executed: bool = False
    stage_projection_executed: bool = False
    persistence_executed: bool = False


def _load_json(path: Path, *, code: str) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise M2ReferenceTruthError(code, path.as_posix()) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M2ReferenceTruthError(code, f"{path.as_posix()}: {exc}") from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise M2ReferenceTruthError(code, f"{path.as_posix()}: root must be object")
    return cast(dict[str, object], raw)


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_SOURCE_INVALID",
            f"{field} must be string-keyed object",
        )
    return cast(dict[str, object], value)


def _required_str(
    mapping: dict[str, object],
    key: str,
    *,
    code: str = "M2_REFERENCE_TRUTH_SOURCE_INVALID",
) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise M2ReferenceTruthError(code, f"{key} must be non-empty string")
    return value


def _required_int(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_SOURCE_INVALID",
            f"{key} must be integer",
        )
    return value


def _required_number(mapping: dict[str, object], key: str) -> float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_SOURCE_INVALID",
            f"{key} must be numeric",
        )
    return float(value)


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError as exc:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_SOURCE_MISSING",
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


def _vector(value: object, *, field: str, length: int) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != length:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_SOURCE_INVALID",
            f"{field} must contain {length} numbers",
        )
    output: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise M2ReferenceTruthError(
                "M2_REFERENCE_TRUTH_SOURCE_INVALID",
                f"{field} must contain only numbers",
            )
        output.append(float(item))
    return tuple(output)


def _matrix(value: object, *, field: str) -> tuple[tuple[float, ...], ...]:
    if not isinstance(value, list) or not value:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_SOURCE_INVALID",
            f"{field} must be non-empty matrix",
        )
    rows = tuple(_vector(row, field=f"{field}[{index}]", length=6) for index, row in enumerate(value))
    if len(rows) != 3:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_SOURCE_INVALID",
            f"{field} must be 3x6",
        )
    return rows


def _identity(value: object, *, field: str) -> ReferenceIdentity:
    raw = _object(value, field=field)
    return ReferenceIdentity(
        aircraft_id=_required_str(raw, "aircraft_id"),
        identity_ref=_required_str(raw, "identity_ref"),
        source_entity_key=_required_str(raw, "source_entity_key"),
    )


def _session_time_us(transform: dict[str, object], source_time_us: int) -> int:
    anchor_segment_time_ns = _required_int(transform, "anchor_segment_time_ns")
    anchor_session_time_us = _required_int(transform, "anchor_session_time_us")
    rate_num = _required_int(transform, "rate_num")
    rate_den = _required_int(transform, "rate_den")
    start_ns = _required_int(transform, "valid_segment_start_ns")
    end_ns = _required_int(transform, "valid_segment_end_ns")
    if rate_num <= 0 or rate_den <= 0:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_TIME_TRANSFORM_INVALID",
            f"rate={rate_num}/{rate_den}",
        )

    source_ns = source_time_us * 1000
    if source_ns < start_ns or source_ns > end_ns:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_TIME_OUTSIDE_DOMAIN",
            f"source_ns={source_ns} domain=[{start_ns},{end_ns}]",
        )
    numerator = (source_ns - anchor_segment_time_ns) * rate_num
    quotient, remainder = divmod(numerator, rate_den)
    if remainder:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_TIME_NON_INTEGRAL",
            f"numerator={numerator} rate_den={rate_den}",
        )
    return anchor_session_time_us + quotient


def _projection_hash(
    *,
    fixture_id: str,
    session_id: str,
    own_identity: ReferenceIdentity,
    target_identity: ReferenceIdentity,
    frame: ReferenceFrameProvenance,
    time_transform_id: str,
    time_transform_hash: str,
    rows: tuple[ReferenceTruthRow, ...],
) -> str:
    payload: dict[str, object] = {
        "fixture_id": fixture_id,
        "session_id": session_id,
        "own_identity": {
            "aircraft_id": own_identity.aircraft_id,
            "identity_ref": own_identity.identity_ref,
            "source_entity_key": own_identity.source_entity_key,
        },
        "target_identity": {
            "aircraft_id": target_identity.aircraft_id,
            "identity_ref": target_identity.identity_ref,
            "source_entity_key": target_identity.source_entity_key,
        },
        "frame_provenance": {
            "position_frame": frame.position_frame,
            "velocity_frame": frame.velocity_frame,
            "own_attitude_frame_ref": frame.own_attitude_frame_ref,
            "sensor_boresight_frame_ref": frame.sensor_boresight_frame_ref,
        },
        "time_transform_id": time_transform_id,
        "time_transform_hash": time_transform_hash,
        "rows": [
            {
                "source_time_us": row.source_time_us,
                "session_time_us": row.session_time_us,
                "own_position_ecef_m": row.own_position_ecef_m,
                "target_position_ecef_m": row.target_position_ecef_m,
                "own_velocity_ecef_mps": row.own_velocity_ecef_mps,
                "target_velocity_ecef_mps": row.target_velocity_ecef_mps,
                "own_attitude_quat": row.own_attitude_quat,
                "sensor_boresight_quat": row.sensor_boresight_quat,
                "relative_state_jacobian": row.relative_state_jacobian,
                "uncertainty_refs": dict(row.uncertainty_refs),
            }
            for row in rows
        ],
    }
    return _canonical_hash(payload)


def load_m2_reference_truth(bundle: Path) -> M2ReferenceTruthProjection:
    """Validate and project the governed M2 reference-truth fixture."""

    manifest = _load_json(
        bundle / "manifest.json",
        code="M2_REFERENCE_TRUTH_MANIFEST_INVALID",
    )
    if manifest.get("schema") != EXPECTED_MANIFEST_SCHEMA:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_MANIFEST_SCHEMA_MISMATCH",
            repr(manifest.get("schema")),
        )
    if manifest.get("fixture_id") != EXPECTED_FIXTURE_ID or bundle.name != EXPECTED_FIXTURE_ID:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_FIXTURE_NOT_GOVERNED",
            f"manifest={manifest.get('fixture_id')!r} directory={bundle.name!r}",
        )
    if manifest.get("fixture_version") != EXPECTED_FIXTURE_VERSION:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_VERSION_UNSUPPORTED",
            repr(manifest.get("fixture_version")),
        )
    if manifest.get("data_classification") != EXPECTED_CLASSIFICATION:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_CLASSIFICATION_FORBIDDEN",
            repr(manifest.get("data_classification")),
        )
    if manifest.get("input_hash_algorithm") != EXPECTED_HASH_ALGORITHM:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_HASH_ALGORITHM_MISMATCH",
            repr(manifest.get("input_hash_algorithm")),
        )
    if manifest.get("input_hash_basis") != [EXPECTED_SOURCE_RELATIVE_PATH]:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_HASH_BASIS_MISMATCH",
            repr(manifest.get("input_hash_basis")),
        )

    authority = _object(manifest.get("authority_refs"), field="authority_refs")
    expected_authority: dict[str, object] = {
        "canonical_authority": EXPECTED_CANONICAL_AUTHORITY,
        "core_baseline": EXPECTED_CORE_BASELINE,
        "metric_codes": list(EXPECTED_METRIC_CODES),
        "metric_input_authority_matrix_sha256": EXPECTED_METRIC_INPUT_AUTHORITY_MATRIX_SHA256,
        "p1_metric_catalog_sha256": EXPECTED_P1_METRIC_CATALOG_SHA256,
        "time_transform_contract": EXPECTED_TIME_TRANSFORM_CONTRACT,
        "uncertainty_contract": EXPECTED_UNCERTAINTY_CONTRACT,
    }
    if authority != expected_authority:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_AUTHORITY_MISMATCH",
            repr(authority),
        )

    files = _object(manifest.get("files"), field="files")
    source_ref = _object(files.get("source"), field="files.source")
    if source_ref.get("path") != EXPECTED_SOURCE_RELATIVE_PATH:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_SOURCE_PATH_MISMATCH",
            repr(source_ref.get("path")),
        )
    source_path = bundle / EXPECTED_SOURCE_RELATIVE_PATH
    source_sha256 = _sha256_file(source_path)
    if source_ref.get("sha256") != source_sha256:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_SOURCE_HASH_MISMATCH",
            f"expected={source_ref.get('sha256')} actual={source_sha256}",
        )
    input_sha256 = _input_hash(source_sha256)
    if manifest.get("input_sha256") != input_sha256:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_INPUT_HASH_MISMATCH",
            f"expected={manifest.get('input_sha256')} actual={input_sha256}",
        )

    source = _load_json(source_path, code="M2_REFERENCE_TRUTH_SOURCE_INVALID")
    if source.get("schema") != EXPECTED_SOURCE_SCHEMA:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_SOURCE_SCHEMA_MISMATCH",
            repr(source.get("schema")),
        )
    if source.get("fixture_id") != EXPECTED_FIXTURE_ID:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_SOURCE_FIXTURE_MISMATCH",
            repr(source.get("fixture_id")),
        )
    if source.get("data_classification") != EXPECTED_CLASSIFICATION:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_CLASSIFICATION_FORBIDDEN",
            repr(source.get("data_classification")),
        )

    session = _object(source.get("session"), field="session")
    session_id = _required_str(session, "session_id")
    source_time_basis = _required_str(session, "source_time_basis")

    identities = _object(source.get("identity_provenance"), field="identity_provenance")
    own_identity = _identity(identities.get("own"), field="identity_provenance.own")
    target_identity = _identity(identities.get("target"), field="identity_provenance.target")

    frame_raw = _object(source.get("frame_provenance"), field="frame_provenance")
    sensor_frame = frame_raw.get("sensor_boresight_frame_ref")
    if sensor_frame is not None and not isinstance(sensor_frame, str):
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_SOURCE_INVALID",
            "sensor_boresight_frame_ref must be string or null",
        )
    frame = ReferenceFrameProvenance(
        position_frame=_required_str(frame_raw, "position_frame"),
        velocity_frame=_required_str(frame_raw, "velocity_frame"),
        own_attitude_frame_ref=_required_str(frame_raw, "own_attitude_frame_ref"),
        sensor_boresight_frame_ref=sensor_frame,
    )

    transform = _object(source.get("time_transform"), field="time_transform")
    time_transform_id = _required_str(transform, "time_transform_id")
    time_transform_hash = _canonical_hash(transform)
    if manifest.get("time_transform_hash") != time_transform_hash:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_TIME_TRANSFORM_HASH_MISMATCH",
            f"expected={manifest.get('time_transform_hash')} actual={time_transform_hash}",
        )

    uncertainty_raw = _object(source.get("uncertainty_records"), field="uncertainty_records")
    if not uncertainty_raw:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_SOURCE_INVALID",
            "uncertainty_records must not be empty",
        )
    uncertainty_records = MappingProxyType(dict(sorted(uncertainty_raw.items())))

    raw_rows = source.get("records")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise M2ReferenceTruthError(
            "M2_REFERENCE_TRUTH_SOURCE_INVALID",
            "records must be non-empty list",
        )

    rows: list[ReferenceTruthRow] = []
    previous_source_time: int | None = None
    for index, raw_row in enumerate(raw_rows):
        row = _object(raw_row, field=f"records[{index}]")
        source_time_us = _required_int(row, "source_time_us")
        if previous_source_time is not None and source_time_us <= previous_source_time:
            raise M2ReferenceTruthError(
                "M2_REFERENCE_TRUTH_TIME_ORDER_INVALID",
                f"index={index} value={source_time_us}",
            )
        previous_source_time = source_time_us
        own = _object(row.get("own"), field=f"records[{index}].own")
        target = _object(row.get("target"), field=f"records[{index}].target")
        uncertainty_refs_raw = _object(
            row.get("uncertainty_refs"),
            field=f"records[{index}].uncertainty_refs",
        )
        uncertainty_refs: dict[str, str] = {}
        for key, value in uncertainty_refs_raw.items():
            if not isinstance(value, str) or value not in uncertainty_raw:
                raise M2ReferenceTruthError(
                    "M2_REFERENCE_TRUTH_UNCERTAINTY_REF_INVALID",
                    f"records[{index}].{key}={value!r}",
                )
            uncertainty_refs[key] = value

        boresight_raw = row.get("sensor_boresight_quat")
        boresight = (
            None
            if boresight_raw is None
            else cast(
                tuple[float, float, float, float],
                _vector(
                    boresight_raw,
                    field=f"records[{index}].sensor_boresight_quat",
                    length=4,
                ),
            )
        )
        rows.append(
            ReferenceTruthRow(
                source_time_us=source_time_us,
                session_time_us=_session_time_us(transform, source_time_us),
                own_position_ecef_m=cast(
                    tuple[float, float, float],
                    _vector(
                        own.get("position_ecef_m"),
                        field=f"records[{index}].own.position_ecef_m",
                        length=3,
                    ),
                ),
                target_position_ecef_m=cast(
                    tuple[float, float, float],
                    _vector(
                        target.get("position_ecef_m"),
                        field=f"records[{index}].target.position_ecef_m",
                        length=3,
                    ),
                ),
                own_velocity_ecef_mps=cast(
                    tuple[float, float, float],
                    _vector(
                        own.get("velocity_ecef_mps"),
                        field=f"records[{index}].own.velocity_ecef_mps",
                        length=3,
                    ),
                ),
                target_velocity_ecef_mps=cast(
                    tuple[float, float, float],
                    _vector(
                        target.get("velocity_ecef_mps"),
                        field=f"records[{index}].target.velocity_ecef_mps",
                        length=3,
                    ),
                ),
                own_attitude_quat=cast(
                    tuple[float, float, float, float],
                    _vector(
                        own.get("attitude_quat"),
                        field=f"records[{index}].own.attitude_quat",
                        length=4,
                    ),
                ),
                sensor_boresight_quat=boresight,
                relative_state_jacobian=_matrix(
                    row.get("relative_state_jacobian"),
                    field=f"records[{index}].relative_state_jacobian",
                ),
                uncertainty_refs=MappingProxyType(dict(sorted(uncertainty_refs.items()))),
            )
        )

    projected_rows = tuple(rows)
    logical_hash = _projection_hash(
        fixture_id=EXPECTED_FIXTURE_ID,
        session_id=session_id,
        own_identity=own_identity,
        target_identity=target_identity,
        frame=frame,
        time_transform_id=time_transform_id,
        time_transform_hash=time_transform_hash,
        rows=projected_rows,
    )
    return M2ReferenceTruthProjection(
        fixture_id=EXPECTED_FIXTURE_ID,
        fixture_version=EXPECTED_FIXTURE_VERSION,
        session_id=session_id,
        source_time_basis=source_time_basis,
        input_sha256=input_sha256,
        source_sha256=source_sha256,
        time_transform_id=time_transform_id,
        time_transform_hash=time_transform_hash,
        own_identity=own_identity,
        target_identity=target_identity,
        frame_provenance=frame,
        uncertainty_records=uncertainty_records,
        rows=projected_rows,
        logical_hash=logical_hash,
    )
