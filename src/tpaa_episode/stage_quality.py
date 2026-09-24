"""M1-WORLD-003 governed Stage quality/status projection."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from tpaa_episode.basic_stage import (
    STAGE_PROJECTOR_VERSION,
    BasicFlightStage,
    project_basic_flight_stages,
)

STAGE_STATUS_VALID = "VALID"
OFFICIAL_MARKER_COVERAGE = 1.0
OFFICIAL_MARKER_CONFIDENCE = 1.0


class StageQualityError(RuntimeError):
    """Deterministic fail-closed Stage quality error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _validate_unit_interval(field: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StageQualityError("M1_STAGE_QUALITY_VALUE_INVALID", f"{field}={value!r}")
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise StageQualityError("M1_STAGE_QUALITY_RANGE_INVALID", f"{field}={value!r}")


@dataclass(frozen=True)
class QualifiedBasicFlightStage:
    """One WORLD-002 Stage enriched with the canonical quality fields."""

    episode_id: str
    stage_id: str
    stage_profile_id: str
    stage_type: str
    stage_order: int
    start_session_time_us: int
    end_session_time_us: int
    precedence_source: str
    detection_method: str
    stage_status: str
    coverage: float
    confidence: float
    detector_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.stage_status, str) or not self.stage_status.strip():
            raise StageQualityError("M1_STAGE_STATUS_INVALID", repr(self.stage_status))
        _validate_unit_interval("coverage", self.coverage)
        _validate_unit_interval("confidence", self.confidence)
        if not isinstance(self.detector_version, str) or not self.detector_version.strip():
            raise StageQualityError(
                "M1_STAGE_DETECTOR_VERSION_INVALID",
                repr(self.detector_version),
            )

    def contains(self, session_time_us: int) -> bool:
        """Return membership using the inherited half-open interval contract."""

        return self.start_session_time_us <= session_time_us < self.end_session_time_us


@dataclass(frozen=True)
class BasicFlightStageQualityProjection:
    """WORLD-003 quality product with downstream execution boundaries explicit."""

    fixture_id: str
    episode_id: str
    stage_profile_id: str
    projector_version: str
    precedence_source: str
    detection_method: str
    interval_semantics: str
    terminator_marker: str
    stages: tuple[QualifiedBasicFlightStage, ...]
    database_persistence_executed: bool = False
    stage_quality_projection_executed: bool = True
    revision_supersede_executed: bool = False
    logical_hash_executed: bool = False
    evidence_refs_projected: bool = False
    world_projection_executed: bool = False
    metric_logic_executed: bool = False


def _qualify(stage: BasicFlightStage) -> QualifiedBasicFlightStage:
    return QualifiedBasicFlightStage(
        episode_id=stage.episode_id,
        stage_id=stage.stage_id,
        stage_profile_id=stage.stage_profile_id,
        stage_type=stage.stage_type,
        stage_order=stage.stage_order,
        start_session_time_us=stage.start_session_time_us,
        end_session_time_us=stage.end_session_time_us,
        precedence_source=stage.precedence_source,
        detection_method=stage.detection_method,
        stage_status=STAGE_STATUS_VALID,
        coverage=OFFICIAL_MARKER_COVERAGE,
        confidence=OFFICIAL_MARKER_CONFIDENCE,
        detector_version=STAGE_PROJECTOR_VERSION,
    )


def project_basic_flight_stage_quality(
    bundle_path: Path,
    *,
    authority_root: Path,
) -> BasicFlightStageQualityProjection:
    """Enrich governed BASIC_FLIGHT_V1 Stages with exact quality/status."""

    base = project_basic_flight_stages(bundle_path, authority_root=authority_root)
    return BasicFlightStageQualityProjection(
        fixture_id=base.fixture_id,
        episode_id=base.episode_id,
        stage_profile_id=base.stage_profile_id,
        projector_version=base.projector_version,
        precedence_source=base.precedence_source,
        detection_method=base.detection_method,
        interval_semantics=base.interval_semantics,
        terminator_marker=base.terminator_marker,
        stages=tuple(_qualify(stage) for stage in base.stages),
    )
