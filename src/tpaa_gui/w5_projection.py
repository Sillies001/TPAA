"""Qt-independent W5 exact-release presentation projections.

This module never calculates a business Metric.  It validates immutable API
bindings and organizes them into the five W5 page lanes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast


class W5ProjectionError(ValueError):
    """Fail-closed W5 presentation contract error."""


@dataclass(frozen=True, slots=True)
class StatusMeaning:
    code: str
    kind: str
    label: str


@dataclass(frozen=True, slots=True)
class SessionOverviewProjection:
    release_id: str
    session_id: str
    context_id: str
    context_version: str
    release_status: str
    episode_id: str
    stages: tuple[dict[str, object], ...]
    aircraft_metrics: tuple[dict[str, object], ...]
    mission_system_metrics: tuple[dict[str, object], ...]
    reference_quality_metrics: tuple[dict[str, object], ...]
    observations: tuple[dict[str, object], ...]
    world_products: tuple[dict[str, object], ...]


_NA = {"N_A", "NOT_APPLICABLE"}
_UNKNOWN = {"UNKNOWN", "UNAVAILABLE", "NOT_EVALUATED", "NOT_OBSERVED"}
_FAILURE = {"FAILED", "FAIL", "INVALID", "SYSTEM_ERROR", "ERROR"}
_REVIEW = {"REVIEW_REQUIRED", "INSUFFICIENT_DATA", "INSUFFICIENT"}
_SUCCESS = {"VALID", "ELIGIBLE", "PUBLISHED", "READY", "PASS", "SUCCEEDED"}


def status_meaning(value: object) -> StatusMeaning:
    """Return distinct N/A, unknown, failure, review, and success semantics."""

    if value is None:
        return StatusMeaning("UNKNOWN", "unknown", "Unknown")
    code = str(value).strip().upper()
    if not code:
        return StatusMeaning("UNKNOWN", "unknown", "Unknown")
    if code in _NA:
        return StatusMeaning(code, "not_applicable", "N/A")
    if code in _UNKNOWN:
        return StatusMeaning(code, "unknown", "Unknown")
    if code in _FAILURE or code.startswith("FAIL"):
        return StatusMeaning(code, "failure", "Failure")
    if code in _REVIEW or code.startswith("INSUFFICIENT"):
        return StatusMeaning(code, "review", code.replace("_", " ").title())
    if code in _SUCCESS:
        return StatusMeaning(code, "success", code.replace("_", " ").title())
    return StatusMeaning(code, "neutral", code.replace("_", " ").title())


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise W5ProjectionError(f"W5_MAPPING_INVALID:{field}")
    return dict(cast(Mapping[str, object], value))


def _rows(value: object, field: str) -> tuple[dict[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise W5ProjectionError(f"W5_ROWS_INVALID:{field}")
    return tuple(_mapping(item, f"{field}[{index}]") for index, item in enumerate(value))


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise W5ProjectionError(f"W5_TEXT_INVALID:{field}")
    return value


def _bound_release(payload: Mapping[str, object], release_id: str, field: str) -> None:
    observed = _text(payload.get("release_id"), f"{field}.release_id")
    if observed != release_id:
        raise W5ProjectionError(f"W5_RELEASE_BINDING_DRIFT:{field}")
    if payload.get("current_latest_fallback_used") is True:
        raise W5ProjectionError(f"W5_LATEST_FALLBACK_FORBIDDEN:{field}")


def build_session_overview(
    *,
    release: Mapping[str, object],
    context: Mapping[str, object],
    topology: Mapping[str, object],
    metrics_payload: Mapping[str, object],
    observations_payload: Mapping[str, object],
    world_graph: Mapping[str, object],
) -> SessionOverviewProjection:
    """Validate and organize exact P1 payloads into independent subject lanes."""

    release_id = _text(release.get("release_id"), "release.release_id")
    for payload, field in (
        (topology, "topology"),
        (metrics_payload, "metrics"),
        (observations_payload, "observations"),
        (world_graph, "world_graph"),
    ):
        _bound_release(payload, release_id, field)
    session = _mapping(topology.get("session"), "topology.session")
    episode = _mapping(topology.get("episode"), "topology.episode")
    session_id = _text(session.get("session_id"), "session.session_id")
    if session_id != _text(release.get("session_id"), "release.session_id"):
        raise W5ProjectionError("W5_SESSION_BINDING_DRIFT")
    context_id = _text(context.get("context_id"), "context.context_id")
    if context_id != _text(release.get("context_id"), "release.context_id"):
        raise W5ProjectionError("W5_CONTEXT_BINDING_DRIFT")

    metrics = _rows(metrics_payload.get("items"), "metrics.items")
    aircraft: list[dict[str, object]] = []
    mission: list[dict[str, object]] = []
    quality: list[dict[str, object]] = []
    for metric in metrics:
        subject = str(metric.get("subject_type", "")).upper()
        lane = str(metric.get("observation_lane", "")).upper()
        code = str(metric.get("metric_code", "")).upper()
        if subject == "MISSION_SYSTEM_INSTANCE" or "MISSION_SYSTEM" in lane:
            mission.append(metric)
        elif any(token in lane or token in code for token in ("QUALITY", "REFERENCE", "ALIGN")):
            quality.append(metric)
        else:
            aircraft.append(metric)

    return SessionOverviewProjection(
        release_id=release_id,
        session_id=session_id,
        context_id=context_id,
        context_version=_text(context.get("context_version"), "context.context_version"),
        release_status=_text(release.get("status"), "release.status"),
        episode_id=_text(episode.get("episode_id"), "episode.episode_id"),
        stages=_rows(topology.get("stages"), "topology.stages"),
        aircraft_metrics=tuple(aircraft),
        mission_system_metrics=tuple(mission),
        reference_quality_metrics=tuple(quality),
        observations=_rows(observations_payload.get("items"), "observations.items"),
        world_products=_rows(world_graph.get("world_products"), "world_graph.world_products"),
    )


def observation_quality_rows(
    projection: SessionOverviewProjection,
) -> tuple[dict[str, object], ...]:
    """Project every observation, including excluded/review records, for P12."""

    rows: list[dict[str, object]] = []
    for item in projection.observations:
        status = status_meaning(item.get("eligibility_status"))
        rows.append(
            {
                "observation_id": item.get("observation_id"),
                "metric_code": item.get("metric_code"),
                "subject": item.get("aircraft_id") or item.get("mission_system_instance_id"),
                "coverage": item.get("coverage"),
                "confidence": item.get("confidence"),
                "eligibility": status.code,
                "status_kind": status.kind,
                "reason": item.get("exclusion_reason_code"),
                "evidence_set_id": item.get("evidence_set_id"),
            }
        )
    return tuple(rows)


def verify_exact_replay(payload: Mapping[str, object], release_id: str) -> str:
    """Accept only exact replay responses with no mutable/latest fallback."""

    _bound_release(payload, release_id, "replay")
    status = _text(payload.get("status"), "replay.status")
    if status not in {"PASS", "EXACT_REPLAY"}:
        raise W5ProjectionError(f"W5_HISTORICAL_REPLAY_FAILED:{status}")
    if payload.get("exact_logical_products_equal") is False:
        raise W5ProjectionError("W5_HISTORICAL_REPLAY_DRIFT")
    return status


__all__ = [
    "SessionOverviewProjection",
    "StatusMeaning",
    "W5ProjectionError",
    "build_session_overview",
    "observation_quality_rows",
    "status_meaning",
    "verify_exact_replay",
]
