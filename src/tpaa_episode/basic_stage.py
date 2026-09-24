"""M1-WORLD-002 governed BASIC_FLIGHT_V1 Stage projection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid5

from tpaa_episode.basic_episode import detect_basic_episode
from tpaa_generated.stage_registry import STAGE_PROFILES
from tpaa_registry import SessionTimeError, build_session_time_projection

STAGE_PROFILE_ID = "BASIC_FLIGHT_V1"
STAGE_PROJECTOR_VERSION = "M1_BASIC_FLIGHT_STAGE_PROJECTOR_V1"
STAGE_NAMESPACE = UUID("a894b95a-2225-441a-8677-0e877ba686e2")
STAGE_PRECEDENCE_SOURCE = "CONTEXT_OFFICIAL_MARKER"
STAGE_DETECTION_METHOD = "CONTEXT"
TERMINATOR_MARKER = "END"
INTERVAL_SEMANTICS = "half-open"
EXPECTED_STAGE_ORDER = (
    "SETUP_ENTRY",
    "EXECUTION",
    "STABILIZATION_RECOVERY",
    "COMPLETION",
)


class BasicStageError(RuntimeError):
    """Deterministic fail-closed BASIC_FLIGHT_V1 Stage error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class BasicFlightStage:
    """One governed half-open Stage interval before quality/revision enrichment."""

    episode_id: str
    stage_id: str
    stage_profile_id: str
    stage_type: str
    stage_order: int
    start_session_time_us: int
    end_session_time_us: int
    precedence_source: str
    detection_method: str

    def contains(self, session_time_us: int) -> bool:
        """Return membership using the frozen half-open interval contract."""

        return self.start_session_time_us <= session_time_us < self.end_session_time_us


@dataclass(frozen=True)
class BasicFlightStageProjection:
    """WORLD-002 projection with explicit boundaries to later M1-C tasks."""

    fixture_id: str
    episode_id: str
    stage_profile_id: str
    projector_version: str
    precedence_source: str
    detection_method: str
    interval_semantics: str
    terminator_marker: str
    stages: tuple[BasicFlightStage, ...]
    database_persistence_executed: bool = False
    stage_quality_projection_executed: bool = False
    revision_supersede_executed: bool = False
    logical_hash_executed: bool = False
    evidence_refs_projected: bool = False
    world_projection_executed: bool = False
    metric_logic_executed: bool = False


def _canonical_text(payload: object) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _authoritative_stage_order() -> tuple[str, ...]:
    for profile in STAGE_PROFILES:
        if profile.get("profile_id") != STAGE_PROFILE_ID:
            continue
        raw = profile.get("ordered_stages")
        if not isinstance(raw, tuple) or not all(isinstance(item, str) for item in raw):
            raise BasicStageError(
                "M1_STAGE_AUTHORITY_INVALID",
                "BASIC_FLIGHT_V1 ordered_stages must be a string tuple",
            )
        order = tuple(raw)
        if order != EXPECTED_STAGE_ORDER:
            raise BasicStageError(
                "M1_STAGE_AUTHORITY_DRIFT",
                repr(order),
            )
        return order
    raise BasicStageError(
        "M1_STAGE_PROFILE_MISSING",
        STAGE_PROFILE_ID,
    )


def _stage_id(
    *,
    episode_id: str,
    stage_type: str,
    stage_order: int,
    start_session_time_us: int,
    end_session_time_us: int,
) -> str:
    identity = {
        "episode_id": episode_id,
        "stage_profile_id": STAGE_PROFILE_ID,
        "stage_type": stage_type,
        "stage_order": stage_order,
        "start_session_time_us": start_session_time_us,
        "end_session_time_us": end_session_time_us,
        "precedence_source": STAGE_PRECEDENCE_SOURCE,
        "detection_method": STAGE_DETECTION_METHOD,
        "projector_version": STAGE_PROJECTOR_VERSION,
    }
    return str(uuid5(STAGE_NAMESPACE, _canonical_text(identity)))


def project_basic_flight_stages(
    bundle_path: Path,
    *,
    authority_root: Path,
) -> BasicFlightStageProjection:
    """Project exact BASIC_FLIGHT_V1 Stage intervals from official markers."""

    order = _authoritative_stage_order()
    try:
        timed = build_session_time_projection(bundle_path)
    except SessionTimeError as exc:
        if exc.code == "M1_SESSION_TIME_CLOCK_ROLLBACK_UNSEGMENTED":
            raise BasicStageError(
                "M1_STAGE_MARKER_ORDER_INVALID",
                exc.detail,
            ) from exc
        raise
    episode = detect_basic_episode(bundle_path, authority_root=authority_root)
    if timed.session_id != episode.session_id:
        raise BasicStageError(
            "M1_STAGE_EPISODE_SESSION_DRIFT",
            f"timed={timed.session_id} episode={episode.session_id}",
        )

    markers = timed.markers
    marker_values = tuple(marker.marker_value for marker in markers)
    allowed_markers = frozenset((*order, TERMINATOR_MARKER))
    unknown = tuple(value for value in marker_values if value not in allowed_markers)
    if unknown:
        raise BasicStageError("M1_STAGE_CODE_UNKNOWN", repr(unknown))
    if TERMINATOR_MARKER not in marker_values:
        raise BasicStageError("M1_STAGE_TERMINATOR_MISSING", repr(marker_values))
    expected_markers = (*order, TERMINATOR_MARKER)
    if marker_values != expected_markers:
        raise BasicStageError("M1_STAGE_MARKER_ORDER_INVALID", repr(marker_values))
    if len(markers) != len(expected_markers):
        raise BasicStageError("M1_STAGE_MARKER_COUNT_INVALID", str(len(markers)))

    marker_times = tuple(marker.session_time_us for marker in markers)
    if (
        marker_times[0] != episode.start_session_time_us
        or marker_times[-1] != episode.end_session_time_us
    ):
        raise BasicStageError(
            "M1_STAGE_EPISODE_BOUNDARY_MISMATCH",
            (
                f"markers=[{marker_times[0]},{marker_times[-1]}] "
                f"episode=[{episode.start_session_time_us},{episode.end_session_time_us}]"
            ),
        )

    stages: list[BasicFlightStage] = []
    for stage_order, (marker, next_marker) in enumerate(zip(markers, markers[1:], strict=False)):
        start = marker.session_time_us
        end = next_marker.session_time_us
        if start >= end:
            raise BasicStageError(
                "M1_STAGE_INTERVAL_INVALID",
                f"stage={marker.marker_value} start={start} end={end}",
            )
        if start < episode.start_session_time_us or end > episode.end_session_time_us:
            raise BasicStageError(
                "M1_STAGE_EPISODE_BOUNDARY_CROSS",
                f"stage={marker.marker_value} interval=[{start},{end})",
            )
        stages.append(
            BasicFlightStage(
                episode_id=episode.episode_id,
                stage_id=_stage_id(
                    episode_id=episode.episode_id,
                    stage_type=marker.marker_value,
                    stage_order=stage_order,
                    start_session_time_us=start,
                    end_session_time_us=end,
                ),
                stage_profile_id=STAGE_PROFILE_ID,
                stage_type=marker.marker_value,
                stage_order=stage_order,
                start_session_time_us=start,
                end_session_time_us=end,
                precedence_source=STAGE_PRECEDENCE_SOURCE,
                detection_method=STAGE_DETECTION_METHOD,
            )
        )

    return BasicFlightStageProjection(
        fixture_id=timed.fixture_id,
        episode_id=episode.episode_id,
        stage_profile_id=STAGE_PROFILE_ID,
        projector_version=STAGE_PROJECTOR_VERSION,
        precedence_source=STAGE_PRECEDENCE_SOURCE,
        detection_method=STAGE_DETECTION_METHOD,
        interval_semantics=INTERVAL_SEMANTICS,
        terminator_marker=TERMINATOR_MARKER,
        stages=tuple(stages),
    )
