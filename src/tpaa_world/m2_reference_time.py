"""M2-WORLD-001 reference/time World products.

The products in this module are in-memory projections over the already governed
M2-DATA-001 and M2-DATA-002 inputs. They mirror the writable fields of the
frozen Core 1.6.0 world.world_product_manifest contract and deliberately do not
create persistence, Stage, Metric, Observation, or publication semantics.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID, uuid5

from tpaa_ingest import (
    M2ReferenceTruthProjection,
    M2TimeAlignmentProjection,
    load_m2_reference_truth,
    load_m2_time_alignment,
)

CORE_SCHEMA_VERSION = "1.6.0"
CORE_WORLD_TABLE = "world.world_product_manifest"
WORLD_POLICY_ID = "WORLD_CAPABILITY_REGISTRY"
WORLD_POLICY_VERSION = "1.0.0"
REFERENCE_WORLD_VERSION = "M2_REFERENCE_TRUTH_WORLD_V1"
TIME_WORLD_VERSION = "M2_TIME_ALIGNMENT_WORLD_V1"
REFERENCE_WORLD_KIND = "TRUTH"
TIME_WORLD_KIND = "MACHINE"
WORLD_STATUS = "READY"
WORLD_NAMESPACE = UUID("be62aa34-df12-44eb-baa3-717d91f99df2")

CORE_WORLD_MANIFEST_FIELDS = (
    "world_product_id",
    "release_id",
    "session_id",
    "episode_id",
    "stage_id",
    "world_kind",
    "subject_id",
    "observer_id",
    "actor_id",
    "aircraft_id",
    "aircraft_instance_id",
    "dataset_id",
    "start_session_time_us",
    "end_session_time_us",
    "status",
    "coverage",
    "confidence",
    "reason_codes",
    "source_authority_signature",
    "world_version",
    "policy_version",
    "artifact_sha256",
    "logical_content_hash",
    "request_hash",
    "created_at",
    "supersedes_id",
)
CORE_WORLD_MANIFEST_WRITABLE_FIELDS = tuple(
    field for field in CORE_WORLD_MANIFEST_FIELDS if field != "created_at"
)


class M2ReferenceTimeWorldError(RuntimeError):
    """Deterministic fail-closed M2 reference/time World error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class CoreWorldManifest:
    """Writable Core 1.6.0 World manifest fields, excluding DB-created timestamp."""

    world_product_id: str
    release_id: str
    session_id: str
    episode_id: str | None
    stage_id: str | None
    world_kind: str
    subject_id: str | None
    observer_id: str | None
    actor_id: str | None
    aircraft_id: str | None
    aircraft_instance_id: str | None
    dataset_id: str | None
    start_session_time_us: int
    end_session_time_us: int
    status: str
    coverage: float
    confidence: float
    reason_codes: tuple[str, ...]
    source_authority_signature: str | None
    world_version: str
    policy_version: str
    artifact_sha256: str | None
    logical_content_hash: str
    request_hash: str
    supersedes_id: str | None


@dataclass(frozen=True)
class M2ReferenceTimeWorld:
    """Two Core-compatible World products plus their frozen upstream projections."""

    reference_manifest: CoreWorldManifest
    time_manifest: CoreWorldManifest
    reference_truth: M2ReferenceTruthProjection
    time_alignment: M2TimeAlignmentProjection
    core_schema_sha256: str
    world_policy_sha256: str
    logical_hash: str
    shadow_schema_created: bool = False
    metric_logic_executed: bool = False
    stage_projection_executed: bool = False
    persistence_executed: bool = False
    observation_projection_executed: bool = False
    release_publication_executed: bool = False


def _load_object(path: Path, *, code: str) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M2ReferenceTimeWorldError(code, f"{path.as_posix()}: {exc}") from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise M2ReferenceTimeWorldError(code, f"{path.as_posix()}: root must be object")
    return cast(dict[str, object], raw)


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise M2ReferenceTimeWorldError(
            "M2_WORLD_AUTHORITY_INVALID",
            f"{field} must be string-keyed object",
        )
    return cast(dict[str, object], value)


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise M2ReferenceTimeWorldError(
            "M2_WORLD_AUTHORITY_MISSING",
            path.as_posix(),
        ) from exc


def _normalize_json(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _normalize_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_json(item) for item in value]
    raise M2ReferenceTimeWorldError(
        "M2_WORLD_NON_CANONICAL_VALUE",
        type(value).__name__,
    )


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        _normalize_json(value),
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
        raise M2ReferenceTimeWorldError(
            "M2_WORLD_UUID_INVALID",
            f"{field}={value!r}",
        ) from exc
    canonical = str(parsed)
    if parsed.int == 0 or canonical != value:
        raise M2ReferenceTimeWorldError(
            "M2_WORLD_UUID_INVALID",
            f"{field}={value!r}",
        )
    return canonical


def _validate_world_authority(authority_root: Path) -> tuple[str, str, str]:
    core_path = authority_root / "CORE_LOGICAL_MODEL.json"
    policy_path = authority_root / "WORLD_CAPABILITY_REGISTRY.json"
    core = _load_object(core_path, code="M2_WORLD_CORE_AUTHORITY_INVALID")
    policy = _load_object(policy_path, code="M2_WORLD_POLICY_AUTHORITY_INVALID")

    if core.get("db_schema_version") != CORE_SCHEMA_VERSION:
        raise M2ReferenceTimeWorldError(
            "M2_WORLD_CORE_SCHEMA_VERSION_MISMATCH",
            repr(core.get("db_schema_version")),
        )
    tables = _object(core.get("tables"), field="CORE_LOGICAL_MODEL.tables")
    table = _object(tables.get(CORE_WORLD_TABLE), field=CORE_WORLD_TABLE)
    raw_fields = table.get("fields")
    if not isinstance(raw_fields, list):
        raise M2ReferenceTimeWorldError(
            "M2_WORLD_CORE_MANIFEST_INVALID",
            "fields must be list",
        )
    field_names: list[str] = []
    for index, raw_field in enumerate(raw_fields):
        field = _object(raw_field, field=f"{CORE_WORLD_TABLE}.fields[{index}]")
        name = field.get("name")
        if not isinstance(name, str) or not name:
            raise M2ReferenceTimeWorldError(
                "M2_WORLD_CORE_MANIFEST_INVALID",
                f"fields[{index}].name",
            )
        field_names.append(name)
    if tuple(field_names) != CORE_WORLD_MANIFEST_FIELDS:
        raise M2ReferenceTimeWorldError(
            "M2_WORLD_CORE_MANIFEST_DRIFT",
            repr(field_names),
        )

    if policy.get("registry_id") != WORLD_POLICY_ID:
        raise M2ReferenceTimeWorldError(
            "M2_WORLD_POLICY_ID_MISMATCH",
            repr(policy.get("registry_id")),
        )
    if policy.get("version") != WORLD_POLICY_VERSION:
        raise M2ReferenceTimeWorldError(
            "M2_WORLD_POLICY_VERSION_MISMATCH",
            repr(policy.get("version")),
        )
    worlds = _object(policy.get("worlds"), field="WORLD_CAPABILITY_REGISTRY.worlds")
    if not isinstance(worlds.get("W"), str) or not isinstance(worlds.get("M"), str):
        raise M2ReferenceTimeWorldError(
            "M2_WORLD_POLICY_WORLD_KIND_MISSING",
            "W/M semantics must be present",
        )
    return (
        _sha256_file(core_path),
        _sha256_file(policy_path),
        f"{WORLD_POLICY_ID}:{WORLD_POLICY_VERSION}",
    )


def _reference_payload(projection: M2ReferenceTruthProjection) -> dict[str, object]:
    return {
        "fixture_id": projection.fixture_id,
        "fixture_version": projection.fixture_version,
        "session_id": projection.session_id,
        "source_time_basis": projection.source_time_basis,
        "input_sha256": projection.input_sha256,
        "source_sha256": projection.source_sha256,
        "time_transform_id": projection.time_transform_id,
        "time_transform_hash": projection.time_transform_hash,
        "own_identity": {
            "aircraft_id": projection.own_identity.aircraft_id,
            "identity_ref": projection.own_identity.identity_ref,
            "source_entity_key": projection.own_identity.source_entity_key,
        },
        "target_identity": {
            "aircraft_id": projection.target_identity.aircraft_id,
            "identity_ref": projection.target_identity.identity_ref,
            "source_entity_key": projection.target_identity.source_entity_key,
        },
        "frame_provenance": {
            "position_frame": projection.frame_provenance.position_frame,
            "velocity_frame": projection.frame_provenance.velocity_frame,
            "own_attitude_frame_ref": projection.frame_provenance.own_attitude_frame_ref,
            "sensor_boresight_frame_ref": (
                projection.frame_provenance.sensor_boresight_frame_ref
            ),
        },
        "uncertainty_records": _normalize_json(projection.uncertainty_records),
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
                "uncertainty_refs": _normalize_json(row.uncertainty_refs),
            }
            for row in projection.rows
        ],
        "upstream_logical_hash": projection.logical_hash,
    }


def _time_payload(projection: M2TimeAlignmentProjection) -> dict[str, object]:
    return {
        "fixture_id": projection.fixture_id,
        "fixture_version": projection.fixture_version,
        "session_id": projection.session_id,
        "session_time_basis": projection.session_time_basis,
        "profile_id": projection.profile_id,
        "max_gap_us": projection.max_gap_us,
        "source_sha256": projection.source_sha256,
        "clock_segments": [
            {
                "segment_id": segment.segment_id,
                "time_transform_id": segment.time_transform_id,
                "sensor_system_instance_id": segment.sensor_system_instance_id,
                "records": [
                    {
                        "sensor_timestamp_mapped_to_session_time_us": (
                            row.sensor_timestamp_mapped_to_session_time_us
                        ),
                        "aligned_session_time_us": row.aligned_session_time_us,
                    }
                    for row in segment.records
                ],
            }
            for segment in projection.clock_segments
        ],
        "latency_records": [
            {
                "sensor_system_instance_id": row.sensor_system_instance_id,
                "sensor_measurement_effective_time_us": (
                    row.sensor_measurement_effective_time_us
                ),
                "referenced_ownship_state_effective_time_us": (
                    row.referenced_ownship_state_effective_time_us
                ),
            }
            for row in projection.latency_records
        ],
        "interpolation_records": [
            {
                "target_pair_id": row.target_pair_id,
                "measurement_time_us": row.measurement_time_us,
                "left_truth_time_us": row.left_truth_time_us,
                "right_truth_time_us": row.right_truth_time_us,
            }
            for row in projection.interpolation_records
        ],
        "uncertainty_records": [
            {
                "reference_name": row.reference_name,
                "representation": row.representation,
                "bound_us": row.bound_us,
                "provenance_ref": row.provenance_ref,
            }
            for row in projection.uncertainty_records
        ],
        "ownship_clock_transform_residual_sigma_us": (
            projection.ownship_clock_transform_residual_sigma_us
        ),
        "target_clock_transform_residual_sigma_us": (
            projection.target_clock_transform_residual_sigma_us
        ),
        "upstream_logical_hash": projection.logical_hash,
    }


def _time_bounds(projection: M2TimeAlignmentProjection) -> tuple[int, int]:
    times: list[int] = []
    for segment in projection.clock_segments:
        for row in segment.records:
            times.extend(
                (
                    row.sensor_timestamp_mapped_to_session_time_us,
                    row.aligned_session_time_us,
                )
            )
    for latency in projection.latency_records:
        times.extend(
            (
                latency.sensor_measurement_effective_time_us,
                latency.referenced_ownship_state_effective_time_us,
            )
        )
    for interpolation in projection.interpolation_records:
        times.extend(
            (
                interpolation.left_truth_time_us,
                interpolation.measurement_time_us,
                interpolation.right_truth_time_us,
            )
        )
    if not times:
        raise M2ReferenceTimeWorldError(
            "M2_WORLD_TIME_CONTENT_EMPTY",
            projection.fixture_id,
        )
    start = min(times)
    end = max(times)
    if end <= start:
        raise M2ReferenceTimeWorldError(
            "M2_WORLD_TIME_RANGE_INVALID",
            f"start={start} end={end}",
        )
    return start, end


def _manifest(
    *,
    release_id: str,
    session_id: str,
    world_kind: str,
    world_version: str,
    logical_content_hash: str,
    source_signature: str,
    start_session_time_us: int,
    end_session_time_us: int,
    policy_version: str,
) -> CoreWorldManifest:
    request_hash = _canonical_hash(
        {
            "release_id": release_id,
            "session_id": session_id,
            "world_kind": world_kind,
            "world_version": world_version,
            "logical_content_hash": logical_content_hash,
            "policy_version": policy_version,
        }
    )
    world_product_id = str(
        uuid5(
            WORLD_NAMESPACE,
            _canonical_bytes(
                {
                    "release_id": release_id,
                    "session_id": session_id,
                    "world_kind": world_kind,
                    "world_version": world_version,
                    "logical_content_hash": logical_content_hash,
                }
            ).decode("ascii"),
        )
    )
    return CoreWorldManifest(
        world_product_id=world_product_id,
        release_id=release_id,
        session_id=session_id,
        episode_id=None,
        stage_id=None,
        world_kind=world_kind,
        subject_id=None,
        observer_id=None,
        actor_id=None,
        aircraft_id=None,
        aircraft_instance_id=None,
        dataset_id=None,
        start_session_time_us=start_session_time_us,
        end_session_time_us=end_session_time_us,
        status=WORLD_STATUS,
        coverage=1.0,
        confidence=1.0,
        reason_codes=(),
        source_authority_signature=source_signature,
        world_version=world_version,
        policy_version=policy_version,
        artifact_sha256=logical_content_hash,
        logical_content_hash=logical_content_hash,
        request_hash=request_hash,
        supersedes_id=None,
    )


def build_m2_reference_time_world(
    reference_truth: M2ReferenceTruthProjection,
    time_alignment: M2TimeAlignmentProjection,
    *,
    authority_root: Path,
    release_id: str,
) -> M2ReferenceTimeWorld:
    """Build replay-stable reference/time World products from frozen M2 inputs."""

    canonical_release_id = _canonical_uuid(release_id, field="release_id")
    if reference_truth.session_id != time_alignment.session_id:
        raise M2ReferenceTimeWorldError(
            "M2_WORLD_SESSION_DRIFT",
            f"reference={reference_truth.session_id} time={time_alignment.session_id}",
        )
    if not reference_truth.rows:
        raise M2ReferenceTimeWorldError(
            "M2_WORLD_REFERENCE_CONTENT_EMPTY",
            reference_truth.fixture_id,
        )
    if len(reference_truth.logical_hash) != 64 or len(time_alignment.logical_hash) != 64:
        raise M2ReferenceTimeWorldError(
            "M2_WORLD_UPSTREAM_HASH_INVALID",
            f"reference={reference_truth.logical_hash} time={time_alignment.logical_hash}",
        )

    core_hash, policy_hash, policy_version = _validate_world_authority(authority_root)
    reference_payload = _reference_payload(reference_truth)
    time_payload = _time_payload(time_alignment)
    reference_hash = _canonical_hash(reference_payload)
    time_hash = _canonical_hash(time_payload)

    reference_start = min(row.session_time_us for row in reference_truth.rows)
    reference_end = max(row.session_time_us for row in reference_truth.rows)
    if reference_end <= reference_start:
        raise M2ReferenceTimeWorldError(
            "M2_WORLD_REFERENCE_RANGE_INVALID",
            f"start={reference_start} end={reference_end}",
        )
    time_start, time_end = _time_bounds(time_alignment)

    reference_signature = _canonical_hash(
        {
            "input_sha256": reference_truth.input_sha256,
            "source_sha256": reference_truth.source_sha256,
            "upstream_logical_hash": reference_truth.logical_hash,
            "core_schema_sha256": core_hash,
            "world_policy_sha256": policy_hash,
        }
    )
    time_signature = _canonical_hash(
        {
            "source_sha256": time_alignment.source_sha256,
            "upstream_logical_hash": time_alignment.logical_hash,
            "core_schema_sha256": core_hash,
            "world_policy_sha256": policy_hash,
        }
    )

    reference_manifest = _manifest(
        release_id=canonical_release_id,
        session_id=reference_truth.session_id,
        world_kind=REFERENCE_WORLD_KIND,
        world_version=REFERENCE_WORLD_VERSION,
        logical_content_hash=reference_hash,
        source_signature=reference_signature,
        start_session_time_us=reference_start,
        end_session_time_us=reference_end,
        policy_version=policy_version,
    )
    time_manifest = _manifest(
        release_id=canonical_release_id,
        session_id=time_alignment.session_id,
        world_kind=TIME_WORLD_KIND,
        world_version=TIME_WORLD_VERSION,
        logical_content_hash=time_hash,
        source_signature=time_signature,
        start_session_time_us=time_start,
        end_session_time_us=time_end,
        policy_version=policy_version,
    )
    logical_hash = _canonical_hash(
        {
            "session_id": reference_truth.session_id,
            "reference_world_hash": reference_hash,
            "time_world_hash": time_hash,
            "core_schema_sha256": core_hash,
            "world_policy_sha256": policy_hash,
        }
    )
    return M2ReferenceTimeWorld(
        reference_manifest=reference_manifest,
        time_manifest=time_manifest,
        reference_truth=reference_truth,
        time_alignment=time_alignment,
        core_schema_sha256=core_hash,
        world_policy_sha256=policy_hash,
        logical_hash=logical_hash,
    )


def project_m2_reference_time_world(
    reference_bundle: Path,
    time_bundle: Path,
    *,
    authority_root: Path,
    release_id: str,
) -> M2ReferenceTimeWorld:
    """Load governed M2 inputs and build their Core-compatible World products."""

    return build_m2_reference_time_world(
        load_m2_reference_truth(reference_bundle),
        load_m2_time_alignment(time_bundle),
        authority_root=authority_root,
        release_id=release_id,
    )
