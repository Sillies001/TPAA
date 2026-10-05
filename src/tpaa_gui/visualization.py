"""Governed presentation-only trajectory and media adapters for PIQB B5."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast


class VisualizationPresentationError(RuntimeError):
    """Fail-closed trajectory/media presentation error."""


@dataclass(frozen=True, slots=True)
class TrajectorySample:
    session_time_us: int
    latitude_deg: float
    longitude_deg: float
    altitude_m: float | None
    source_release_id: str
    evidence_ref: str | None


@dataclass(frozen=True, slots=True)
class MediaReference:
    media_id: str
    media_type: str
    uri: str
    source_release_id: str
    evidence_ref: str | None


@dataclass(frozen=True, slots=True)
class TrajectoryPresentation:
    release_id: str
    samples: tuple[TrajectorySample, ...]
    media: tuple[MediaReference, ...]
    time_semantics: str
    business_recompute: bool
    persistence_access: bool
    mutable_alias_resolution: bool


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise VisualizationPresentationError(f"VIS_MAPPING_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise VisualizationPresentationError(f"VIS_TEXT_INVALID:{field}")
    return value


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise VisualizationPresentationError(f"VIS_INTEGER_INVALID:{field}")
    return value


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VisualizationPresentationError(f"VIS_NUMBER_INVALID:{field}")
    return float(value)


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field)


def _optional_number(value: object, field: str) -> float | None:
    if value is None:
        return None
    return _number(value, field)


def build_trajectory_presentation(
    payload: Mapping[str, object],
    *,
    expected_release_id: str,
) -> TrajectoryPresentation:
    """Validate an exact-release presentation payload without domain recomputation."""

    if payload.get("schema") != "TPAA_TRAJECTORY_PRESENTATION_V1":
        raise VisualizationPresentationError("VIS_SCHEMA_INVALID")
    release_id = _text(payload.get("release_id"), "release_id")
    if release_id != expected_release_id:
        raise VisualizationPresentationError("VIS_RELEASE_ID_MISMATCH")
    if payload.get("time_semantics") != "SESSION_TIME":
        raise VisualizationPresentationError("VIS_TIME_SEMANTICS_INVALID")
    if payload.get("business_recompute") is not False:
        raise VisualizationPresentationError("VIS_BUSINESS_RECOMPUTE_FORBIDDEN")
    if payload.get("persistence_access") is not False:
        raise VisualizationPresentationError("VIS_PERSISTENCE_ACCESS_FORBIDDEN")
    if payload.get("mutable_alias_resolution") is not False:
        raise VisualizationPresentationError("VIS_MUTABLE_ALIAS_FORBIDDEN")

    raw_samples = payload.get("samples")
    if not isinstance(raw_samples, list):
        raise VisualizationPresentationError("VIS_SAMPLES_INVALID")
    samples: list[TrajectorySample] = []
    previous_time: int | None = None
    for index, raw in enumerate(raw_samples):
        sample = _mapping(raw, f"samples[{index}]")
        session_time_us = _integer(
            sample.get("session_time_us"),
            f"samples[{index}].session_time_us",
        )
        if session_time_us < 0 or (
            previous_time is not None and session_time_us < previous_time
        ):
            raise VisualizationPresentationError("VIS_SAMPLE_TIME_ORDER_INVALID")
        previous_time = session_time_us
        latitude = _number(sample.get("latitude_deg"), f"samples[{index}].latitude_deg")
        longitude = _number(sample.get("longitude_deg"), f"samples[{index}].longitude_deg")
        if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
            raise VisualizationPresentationError("VIS_COORDINATE_RANGE_INVALID")
        source_release_id = _text(
            sample.get("source_release_id"),
            f"samples[{index}].source_release_id",
        )
        if source_release_id != release_id:
            raise VisualizationPresentationError("VIS_SAMPLE_RELEASE_MISMATCH")
        samples.append(
            TrajectorySample(
                session_time_us=session_time_us,
                latitude_deg=latitude,
                longitude_deg=longitude,
                altitude_m=_optional_number(
                    sample.get("altitude_m"),
                    f"samples[{index}].altitude_m",
                ),
                source_release_id=source_release_id,
                evidence_ref=_optional_text(
                    sample.get("evidence_ref"),
                    f"samples[{index}].evidence_ref",
                ),
            )
        )

    raw_media = payload.get("media")
    if not isinstance(raw_media, list):
        raise VisualizationPresentationError("VIS_MEDIA_INVALID")
    media: list[MediaReference] = []
    for index, raw in enumerate(raw_media):
        item = _mapping(raw, f"media[{index}]")
        source_release_id = _text(
            item.get("source_release_id"),
            f"media[{index}].source_release_id",
        )
        if source_release_id != release_id:
            raise VisualizationPresentationError("VIS_MEDIA_RELEASE_MISMATCH")
        media.append(
            MediaReference(
                media_id=_text(item.get("media_id"), f"media[{index}].media_id"),
                media_type=_text(item.get("media_type"), f"media[{index}].media_type"),
                uri=_text(item.get("uri"), f"media[{index}].uri"),
                source_release_id=source_release_id,
                evidence_ref=_optional_text(
                    item.get("evidence_ref"),
                    f"media[{index}].evidence_ref",
                ),
            )
        )

    return TrajectoryPresentation(
        release_id=release_id,
        samples=tuple(samples),
        media=tuple(media),
        time_semantics="SESSION_TIME",
        business_recompute=False,
        persistence_access=False,
        mutable_alias_resolution=False,
    )


def build_2d_polyline(
    presentation: TrajectoryPresentation,
) -> tuple[tuple[float, float], ...]:
    """Project exact stored geodetic coordinates to a 2D lon/lat presentation lane."""

    return tuple(
        (sample.longitude_deg, sample.latitude_deg)
        for sample in presentation.samples
    )


def build_cesium_trajectory_packets(
    presentation: TrajectoryPresentation,
) -> list[dict[str, object]]:
    """Create deterministic Cesium-ready relative-time packets for presentation only."""

    if not presentation.samples:
        return [
            {
                "id": "document",
                "version": "1.0",
                "name": f"TPAA release {presentation.release_id}",
            }
        ]
    origin_us = presentation.samples[0].session_time_us
    positions: list[float] = []
    for sample in presentation.samples:
        positions.extend(
            [
                (sample.session_time_us - origin_us) / 1_000_000.0,
                sample.longitude_deg,
                sample.latitude_deg,
                0.0 if sample.altitude_m is None else sample.altitude_m,
            ]
        )
    return [
        {
            "id": "document",
            "version": "1.0",
            "name": f"TPAA release {presentation.release_id}",
            "properties": {
                "tpaaTimeSemantics": "SESSION_TIME_RELATIVE_ONLY",
                "tpaaReleaseId": presentation.release_id,
            },
        },
        {
            "id": f"trajectory:{presentation.release_id}",
            "name": "TPAA exact-release trajectory",
            "position": {
                "epoch": "1970-01-01T00:00:00Z",
                "cartographicDegrees": positions,
            },
            "properties": {
                "tpaaRelativeEpochIsNotUtcFact": True,
                "tpaaSessionTimeOriginUs": origin_us,
                "tpaaReleaseId": presentation.release_id,
            },
        },
    ]
