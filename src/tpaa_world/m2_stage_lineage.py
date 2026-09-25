"""M2-WORLD-003 Basic Flight Stage/World lineage and status.

This module binds the already governed M1 BASIC_FLIGHT_V1 Stage quality
projection to the M2-WORLD-001/002 logical products. It is an in-memory lineage
projection only: frozen Stage authority and existing World manifests are never
rewritten to manufacture one stage id for a World product that may span
multiple Stage intervals.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from tpaa_episode import (
    BasicFlightStageQualityProjection,
    QualifiedBasicFlightStage,
    detect_basic_episode,
    project_basic_flight_stage_quality,
)

from .m2_radar_sensor import M2RadarSensorWorld, project_m2_radar_sensor_world
from .m2_reference_time import (
    CoreWorldManifest,
    M2ReferenceTimeWorld,
    project_m2_reference_time_world,
)

CORE_SCHEMA_VERSION = "1.6.0"
STAGE_TABLE = "episode.episode_stage"
STAGE_REGISTRY_ID = "STAGE_REGISTRY"
STAGE_REGISTRY_VERSION = "1.1.0"
STAGE_PROFILE_ID = "BASIC_FLIGHT_V1"
EXPECTED_STAGE_ORDER = (
    "SETUP_ENTRY",
    "EXECUTION",
    "STABILIZATION_RECOVERY",
    "COMPLETION",
)
EXPECTED_STAGE_PERSISTED_FIELDS = (
    "stage_id",
    "episode_id",
    "stage_type",
    "stage_order",
    "start_session_time_us",
    "end_session_time_us",
    "detection_method",
    "stage_status",
    "coverage",
    "confidence",
    "detector_version",
    "supersedes_stage_id",
    "created_at",
)
WORLD_ROLES = (
    "REFERENCE_TRUTH_WORLD",
    "TIME_ALIGNMENT_WORLD",
    "RADAR_SENSOR_WORLD",
)


class M2StageWorldLineageError(RuntimeError):
    """Deterministic fail-closed M2 Stage/World lineage error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class M2StageWorldLineageRecord:
    """One authoritative Stage overlap for one existing M2 World product."""

    world_role: str
    world_product_id: str
    world_version: str
    world_status: str
    world_logical_content_hash: str
    episode_id: str
    stage_id: str
    stage_type: str
    stage_order: int
    stage_status: str
    stage_coverage: float
    stage_confidence: float
    detector_version: str
    overlap_start_session_time_us: int
    overlap_end_session_time_us: int
    overlap_duration_us: int


@dataclass(frozen=True)
class M2StageWorldLineageSummary:
    """Complete Stage coverage/status summary for one M2 World product."""

    world_role: str
    world_product_id: str
    world_version: str
    world_status: str
    world_logical_content_hash: str
    lineage_coverage: float
    lineage_confidence: float
    stage_ids: tuple[str, ...]
    stage_types: tuple[str, ...]
    logical_hash: str


@dataclass(frozen=True)
class M2StageWorldLineage:
    """Replay-stable M2 Basic Flight Stage/World lineage projection."""

    episode_id: str
    session_id: str
    stage_profile_id: str
    stage_registry_sha256: str
    core_schema_sha256: str
    stage_projection: BasicFlightStageQualityProjection
    reference_time_world: M2ReferenceTimeWorld
    radar_sensor_world: M2RadarSensorWorld
    summaries: tuple[M2StageWorldLineageSummary, ...]
    records: tuple[M2StageWorldLineageRecord, ...]
    status: str
    coverage: float
    confidence: float
    logical_hash: str
    stage_authority_rewritten: bool = False
    world_manifest_rewritten: bool = False
    persistence_executed: bool = False
    metric_logic_executed: bool = False
    observation_projection_executed: bool = False
    release_publication_executed: bool = False


def _load_object(path: Path, *, code: str) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M2StageWorldLineageError(code, f"{path.as_posix()}: {exc}") from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise M2StageWorldLineageError(code, f"{path.as_posix()}: root must be object")
    return cast(dict[str, object], raw)


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_AUTHORITY_INVALID",
            f"{field} must be string-keyed object",
        )
    return cast(dict[str, object], value)


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_AUTHORITY_MISSING",
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


def _validate_stage_authority(authority_root: Path) -> tuple[str, str]:
    stage_path = authority_root / "STAGE_REGISTRY.json"
    core_path = authority_root / "CORE_LOGICAL_MODEL.json"
    stage = _load_object(stage_path, code="M2_STAGE_WORLD_STAGE_AUTHORITY_INVALID")
    core = _load_object(core_path, code="M2_STAGE_WORLD_CORE_AUTHORITY_INVALID")

    if stage.get("registry_id") != STAGE_REGISTRY_ID:
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_STAGE_REGISTRY_ID_MISMATCH",
            repr(stage.get("registry_id")),
        )
    if stage.get("version") != STAGE_REGISTRY_VERSION:
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_STAGE_REGISTRY_VERSION_MISMATCH",
            repr(stage.get("version")),
        )
    governance = _object(stage.get("governance"), field="STAGE_REGISTRY.governance")
    if governance.get("time_interval") != "half-open [start_session_time_us,end_session_time_us)":
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_INTERVAL_AUTHORITY_DRIFT",
            repr(governance.get("time_interval")),
        )
    profiles = _object(stage.get("profiles"), field="STAGE_REGISTRY.profiles")
    basic = _object(profiles.get(STAGE_PROFILE_ID), field=STAGE_PROFILE_ID)
    raw_order = basic.get("ordered_stages")
    if raw_order != list(EXPECTED_STAGE_ORDER):
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_PROFILE_ORDER_DRIFT",
            repr(raw_order),
        )

    if core.get("db_schema_version") != CORE_SCHEMA_VERSION:
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_CORE_SCHEMA_VERSION_MISMATCH",
            repr(core.get("db_schema_version")),
        )
    tables = _object(core.get("tables"), field="CORE_LOGICAL_MODEL.tables")
    episode_stage = _object(tables.get(STAGE_TABLE), field=STAGE_TABLE)
    raw_fields = episode_stage.get("fields")
    if not isinstance(raw_fields, list):
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_STAGE_TABLE_INVALID",
            "fields must be list",
        )
    field_names: list[str] = []
    for index, raw_field in enumerate(raw_fields):
        field = _object(raw_field, field=f"{STAGE_TABLE}.fields[{index}]")
        name = field.get("name")
        if not isinstance(name, str) or not name:
            raise M2StageWorldLineageError(
                "M2_STAGE_WORLD_STAGE_TABLE_INVALID",
                f"fields[{index}].name",
            )
        field_names.append(name)
    if tuple(field_names) != EXPECTED_STAGE_PERSISTED_FIELDS:
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_STAGE_TABLE_DRIFT",
            repr(field_names),
        )
    return _sha256_file(stage_path), _sha256_file(core_path)


def _validate_stage_projection(
    projection: BasicFlightStageQualityProjection,
) -> None:
    if projection.stage_profile_id != STAGE_PROFILE_ID:
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_PROFILE_MISMATCH",
            projection.stage_profile_id,
        )
    if projection.interval_semantics != "half-open":
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_INTERVAL_SEMANTICS_MISMATCH",
            projection.interval_semantics,
        )
    if tuple(stage.stage_type for stage in projection.stages) != EXPECTED_STAGE_ORDER:
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_STAGE_ORDER_MISMATCH",
            repr(tuple(stage.stage_type for stage in projection.stages)),
        )
    if tuple(stage.stage_order for stage in projection.stages) != (0, 1, 2, 3):
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_STAGE_ORDER_INDEX_MISMATCH",
            repr(tuple(stage.stage_order for stage in projection.stages)),
        )
    previous_end: int | None = None
    for stage in projection.stages:
        if (
            stage.stage_status != "VALID"
            or not math.isclose(stage.coverage, 1.0)
            or not math.isclose(stage.confidence, 1.0)
            or not stage.detector_version
            or stage.start_session_time_us >= stage.end_session_time_us
        ):
            raise M2StageWorldLineageError(
                "M2_STAGE_WORLD_STAGE_QUALITY_INVALID",
                stage.stage_id,
            )
        if previous_end is not None and stage.start_session_time_us != previous_end:
            raise M2StageWorldLineageError(
                "M2_STAGE_WORLD_STAGE_GAP_OR_OVERLAP",
                stage.stage_id,
            )
        previous_end = stage.end_session_time_us


def _bind_world(
    role: str,
    manifest: CoreWorldManifest,
    stages: tuple[QualifiedBasicFlightStage, ...],
    *,
    episode_id: str,
) -> tuple[M2StageWorldLineageSummary, tuple[M2StageWorldLineageRecord, ...]]:
    if role not in WORLD_ROLES:
        raise M2StageWorldLineageError("M2_STAGE_WORLD_ROLE_INVALID", role)
    if manifest.status not in {"READY", "PARTIAL"}:
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_WORLD_STATUS_INVALID",
            f"{role}={manifest.status}",
        )
    if manifest.episode_id is not None or manifest.stage_id is not None:
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_MANIFEST_ALREADY_SCOPED",
            role,
        )
    duration = manifest.end_session_time_us - manifest.start_session_time_us
    if duration <= 0:
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_WORLD_RANGE_INVALID",
            role,
        )

    records: list[M2StageWorldLineageRecord] = []
    for stage in stages:
        start = max(manifest.start_session_time_us, stage.start_session_time_us)
        end = min(manifest.end_session_time_us, stage.end_session_time_us)
        if start >= end:
            continue
        records.append(
            M2StageWorldLineageRecord(
                world_role=role,
                world_product_id=manifest.world_product_id,
                world_version=manifest.world_version,
                world_status=manifest.status,
                world_logical_content_hash=manifest.logical_content_hash,
                episode_id=episode_id,
                stage_id=stage.stage_id,
                stage_type=stage.stage_type,
                stage_order=stage.stage_order,
                stage_status=stage.stage_status,
                stage_coverage=stage.coverage,
                stage_confidence=stage.confidence,
                detector_version=stage.detector_version,
                overlap_start_session_time_us=start,
                overlap_end_session_time_us=end,
                overlap_duration_us=end - start,
            )
        )
    covered = sum(record.overlap_duration_us for record in records)
    lineage_coverage = covered / duration
    if not records or not math.isclose(lineage_coverage, 1.0, abs_tol=1e-12):
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_COVERAGE_INCOMPLETE",
            f"{role} coverage={lineage_coverage}",
        )
    if any(record.stage_status != "VALID" for record in records):
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_STAGE_STATUS_INVALID",
            role,
        )
    lineage_confidence = min(record.stage_confidence for record in records)
    logical_hash = _canonical_hash(
        {
            "world_role": role,
            "world_version": manifest.world_version,
            "world_status": manifest.status,
            "world_logical_content_hash": manifest.logical_content_hash,
            "episode_id": episode_id,
            "lineage_coverage": lineage_coverage,
            "lineage_confidence": lineage_confidence,
            "stages": [
                {
                    "stage_id": record.stage_id,
                    "stage_type": record.stage_type,
                    "stage_order": record.stage_order,
                    "stage_status": record.stage_status,
                    "stage_coverage": record.stage_coverage,
                    "stage_confidence": record.stage_confidence,
                    "detector_version": record.detector_version,
                    "overlap_start_session_time_us": (
                        record.overlap_start_session_time_us
                    ),
                    "overlap_end_session_time_us": record.overlap_end_session_time_us,
                }
                for record in records
            ],
        }
    )
    return (
        M2StageWorldLineageSummary(
            world_role=role,
            world_product_id=manifest.world_product_id,
            world_version=manifest.world_version,
            world_status=manifest.status,
            world_logical_content_hash=manifest.logical_content_hash,
            lineage_coverage=lineage_coverage,
            lineage_confidence=lineage_confidence,
            stage_ids=tuple(record.stage_id for record in records),
            stage_types=tuple(record.stage_type for record in records),
            logical_hash=logical_hash,
        ),
        tuple(records),
    )


def build_m2_stage_world_lineage(
    stage_projection: BasicFlightStageQualityProjection,
    *,
    stage_session_id: str,
    reference_time_world: M2ReferenceTimeWorld,
    radar_sensor_world: M2RadarSensorWorld,
    authority_root: Path,
) -> M2StageWorldLineage:
    """Bind frozen Basic Flight Stage authority to existing M2 World products."""

    stage_registry_hash, core_hash = _validate_stage_authority(authority_root)
    _validate_stage_projection(stage_projection)

    manifests = (
        ("REFERENCE_TRUTH_WORLD", reference_time_world.reference_manifest),
        ("TIME_ALIGNMENT_WORLD", reference_time_world.time_manifest),
        ("RADAR_SENSOR_WORLD", radar_sensor_world.manifest),
    )
    sessions = {manifest.session_id for _, manifest in manifests}
    if sessions != {stage_session_id}:
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_SESSION_DRIFT",
            f"stage={stage_session_id} worlds={sorted(sessions)}",
        )
    if reference_time_world.core_schema_sha256 != core_hash:
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_REFERENCE_CORE_HASH_DRIFT",
            reference_time_world.core_schema_sha256,
        )
    if radar_sensor_world.core_schema_sha256 != core_hash:
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_RADAR_CORE_HASH_DRIFT",
            radar_sensor_world.core_schema_sha256,
        )

    summaries: list[M2StageWorldLineageSummary] = []
    records: list[M2StageWorldLineageRecord] = []
    for role, manifest in manifests:
        summary, bound = _bind_world(
            role,
            manifest,
            stage_projection.stages,
            episode_id=stage_projection.episode_id,
        )
        summaries.append(summary)
        records.extend(bound)

    coverage = min(summary.lineage_coverage for summary in summaries)
    confidence = min(summary.lineage_confidence for summary in summaries)
    status = (
        "READY"
        if all(summary.world_status == "READY" for summary in summaries)
        else "PARTIAL"
    )
    logical_hash = _canonical_hash(
        {
            "episode_id": stage_projection.episode_id,
            "session_id": stage_session_id,
            "stage_profile_id": stage_projection.stage_profile_id,
            "stage_registry_sha256": stage_registry_hash,
            "core_schema_sha256": core_hash,
            "status": status,
            "coverage": coverage,
            "confidence": confidence,
            "summaries": [
                {
                    "world_role": summary.world_role,
                    "world_version": summary.world_version,
                    "world_status": summary.world_status,
                    "world_logical_content_hash": summary.world_logical_content_hash,
                    "lineage_coverage": summary.lineage_coverage,
                    "lineage_confidence": summary.lineage_confidence,
                    "stage_ids": summary.stage_ids,
                    "stage_types": summary.stage_types,
                    "logical_hash": summary.logical_hash,
                }
                for summary in summaries
            ],
        }
    )
    return M2StageWorldLineage(
        episode_id=stage_projection.episode_id,
        session_id=stage_session_id,
        stage_profile_id=stage_projection.stage_profile_id,
        stage_registry_sha256=stage_registry_hash,
        core_schema_sha256=core_hash,
        stage_projection=stage_projection,
        reference_time_world=reference_time_world,
        radar_sensor_world=radar_sensor_world,
        summaries=tuple(summaries),
        records=tuple(records),
        status=status,
        coverage=coverage,
        confidence=confidence,
        logical_hash=logical_hash,
    )


def project_m2_stage_world_lineage(
    stage_bundle: Path,
    reference_bundle: Path,
    time_bundle: Path,
    mission_bundle: Path,
    alignment_bundle: Path,
    *,
    authority_root: Path,
    release_id: str,
) -> M2StageWorldLineage:
    """Project M2-WORLD-003 from frozen Stage and M2 World inputs."""

    episode = detect_basic_episode(stage_bundle, authority_root=authority_root)
    stage_projection = project_basic_flight_stage_quality(
        stage_bundle,
        authority_root=authority_root,
    )
    if stage_projection.episode_id != episode.episode_id:
        raise M2StageWorldLineageError(
            "M2_STAGE_WORLD_EPISODE_DRIFT",
            (
                f"stage={stage_projection.episode_id} "
                f"episode={episode.episode_id}"
            ),
        )
    reference_time_world = project_m2_reference_time_world(
        reference_bundle,
        time_bundle,
        authority_root=authority_root,
        release_id=release_id,
    )
    radar_sensor_world = project_m2_radar_sensor_world(
        mission_bundle,
        alignment_bundle,
        authority_root=authority_root,
        release_id=release_id,
    )
    return build_m2_stage_world_lineage(
        stage_projection,
        stage_session_id=episode.session_id,
        reference_time_world=reference_time_world,
        radar_sensor_world=radar_sensor_world,
        authority_root=authority_root,
    )
