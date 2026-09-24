"""M1-DATA-003 explicit Source Time to Session Time projection.

The M1 fixture profile supplies source clock values as integer microseconds and
an explicit OFFSET_US fixture transform. This module maps that controlled input
onto the frozen Canonical ANCHORED_RATIONAL time-transform shape using only
integer arithmetic. It never reads host timezone, locale, or wall clock.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid5

from tpaa_ingest import GOVERNED_FIXTURE_IDS, load_synthetic_fixture_bundle

from .source_registration import register_synthetic_fixture

EXPECTED_CONTEXT_SCHEMA = "TPAA_M1_SYNTHETIC_CONTEXT_V1"
EXPECTED_SOURCE_TIME_BASIS = "SOURCE_US"
EXPECTED_FIXTURE_TRANSFORM_KIND = "OFFSET_US"
CANONICAL_TIME_TRANSFORM_MODEL = "ANCHORED_RATIONAL"
TIME_TRANSFORM_METHOD = "M1_FIXTURE_OFFSET_US"
TIME_TRANSFORM_VERSION = "1.0.0"
RATE_NUM = 1
RATE_DEN = 1000
TIME_ALIGNMENT_NAMESPACE = UUID("b125af1f-2d66-4ca8-a934-9b2fa9154438")

_UNSIGNED_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_SIGNED_DECIMAL = re.compile(r"(?:0|-?[1-9][0-9]*)\Z")


class SessionTimeError(RuntimeError):
    """Deterministic fail-closed Session Time ingest error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class FixtureOffsetTransform:
    """Controlled fixture transform before Canonical projection."""

    offset_us: int


@dataclass(frozen=True)
class CanonicalTimeTransformProjection:
    """Canonical-compatible registry.time_transform projection."""

    source_clock_segment_id: str
    time_transform_id: str
    model: str
    anchor_segment_time_ns: int
    anchor_session_time_us: int
    rate_num: int
    rate_den: int
    valid_segment_start_ns: int
    valid_segment_end_ns: int
    residual_rms_us: float
    residual_p95_us: float
    confidence: float
    method: str
    version: str
    transform_hash: str


@dataclass(frozen=True)
class SessionTimedSourceRow:
    """Source row ordinal with explicit authoritative Session Time."""

    source_stream_ordinal: int
    source_time_us: str
    session_time_us: int


@dataclass(frozen=True)
class SessionTimedSourceMarker:
    """Source marker ordinal with explicit authoritative Session Time."""

    marker_ordinal: int
    source_time_us: str
    session_time_us: int
    marker_value: str


@dataclass(frozen=True)
class SessionTimeProjection:
    """Complete M1-DATA-003 projection for one governed fixture."""

    fixture_id: str
    session_id: str
    source_id: str
    source_stream_id: str
    source_time_basis: str
    start_session_time_us: int
    end_session_time_us: int
    transform: CanonicalTimeTransformProjection
    rows: tuple[SessionTimedSourceRow, ...]
    markers: tuple[SessionTimedSourceMarker, ...]
    logical_hash: str
    database_persistence_executed: bool = False
    canonical_flight_channel_projection_executed: bool = False
    stage_projection_executed: bool = False
    metric_logic_executed: bool = False


def parse_source_time_us(value: str) -> int:
    """Parse canonical non-negative ASCII decimal source microseconds."""

    if _UNSIGNED_DECIMAL.fullmatch(value) is None:
        raise SessionTimeError(
            "M1_SESSION_TIME_SOURCE_FORMAT_INVALID",
            repr(value),
        )
    return int(value, 10)


def parse_offset_us(value: object) -> int:
    """Parse canonical signed ASCII decimal fixture offset."""

    if not isinstance(value, str) or _SIGNED_DECIMAL.fullmatch(value) is None:
        raise SessionTimeError(
            "M1_SESSION_TIME_OFFSET_FORMAT_INVALID",
            repr(value),
        )
    return int(value, 10)


def validate_source_clock_sequence(values: Sequence[int]) -> None:
    """Reject source-clock rollback before any global timestamp reordering."""

    for previous, current in zip(values, values[1:], strict=False):
        if current < previous:
            raise SessionTimeError(
                "M1_SESSION_TIME_CLOCK_ROLLBACK_UNSEGMENTED",
                f"previous={previous} current={current}",
            )


def apply_session_time_us(
    transform: CanonicalTimeTransformProjection,
    segment_time_ns: int,
) -> int:
    """Apply one exact anchored rational transform without implicit rounding."""

    if not (
        transform.valid_segment_start_ns
        <= segment_time_ns
        <= transform.valid_segment_end_ns
    ):
        raise SessionTimeError(
            "M1_SESSION_TIME_OUTSIDE_TRANSFORM_DOMAIN",
            (
                f"value={segment_time_ns} "
                f"domain=[{transform.valid_segment_start_ns},"
                f"{transform.valid_segment_end_ns}]"
            ),
        )
    numerator = (
        (segment_time_ns - transform.anchor_segment_time_ns)
        * transform.rate_num
    )
    quotient, remainder = divmod(numerator, transform.rate_den)
    if remainder != 0:
        raise SessionTimeError(
            "M1_SESSION_TIME_NON_INTEGRAL_TRANSFORM",
            (
                f"numerator={numerator} rate_den={transform.rate_den} "
                f"remainder={remainder}"
            ),
        )
    return transform.anchor_session_time_us + quotient


def _load_json(path: Path) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SessionTimeError(
            "M1_SESSION_TIME_CONTEXT_MISSING",
            path.as_posix(),
        ) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SessionTimeError(
            "M1_SESSION_TIME_CONTEXT_CORRUPT",
            f"{path.as_posix()}: {exc}",
        ) from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise SessionTimeError(
            "M1_SESSION_TIME_CONTEXT_CORRUPT",
            f"{path.as_posix()}: JSON root must be string-keyed object",
        )
    return dict(raw)


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise SessionTimeError(
            "M1_SESSION_TIME_CONTEXT_INVALID",
            f"{field} must be string-keyed object",
        )
    return dict(value)


def _fixture_transform(context: dict[str, object]) -> FixtureOffsetTransform:
    if context.get("schema") != EXPECTED_CONTEXT_SCHEMA:
        raise SessionTimeError(
            "M1_SESSION_TIME_CONTEXT_SCHEMA_MISMATCH",
            repr(context.get("schema")),
        )
    raw = _object(
        context.get("source_time_transform"),
        field="source_time_transform",
    )
    if raw.get("kind") != EXPECTED_FIXTURE_TRANSFORM_KIND:
        raise SessionTimeError(
            "M1_SESSION_TIME_TRANSFORM_KIND_UNSUPPORTED",
            repr(raw.get("kind")),
        )
    return FixtureOffsetTransform(offset_us=parse_offset_us(raw.get("offset_us")))


def _stable_uuid(label: str) -> str:
    return str(uuid5(TIME_ALIGNMENT_NAMESPACE, label))


def _hash_payload(payload: dict[str, object]) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _build_transform(
    *,
    source_stream_id: str,
    start_source_time_us: int,
    end_source_time_us: int,
    offset_us: int,
) -> CanonicalTimeTransformProjection:
    start_ns = start_source_time_us * 1000
    end_ns = end_source_time_us * 1000
    if end_ns <= start_ns:
        raise SessionTimeError(
            "M1_SESSION_TIME_SEGMENT_RANGE_INVALID",
            f"start_ns={start_ns} end_ns={end_ns}",
        )

    source_clock_segment_id = _stable_uuid(
        f"source-clock-segment|{source_stream_id}|1|{start_ns}|{end_ns}"
    )
    transform_fields: dict[str, object] = {
        "source_clock_segment_id": source_clock_segment_id,
        "model": CANONICAL_TIME_TRANSFORM_MODEL,
        "anchor_segment_time_ns": start_ns,
        "anchor_session_time_us": start_source_time_us + offset_us,
        "rate_num": RATE_NUM,
        "rate_den": RATE_DEN,
        "valid_segment_start_ns": start_ns,
        "valid_segment_end_ns": end_ns,
        "residual_rms_us": 0.0,
        "residual_p95_us": 0.0,
        "confidence": 1.0,
        "method": TIME_TRANSFORM_METHOD,
        "version": TIME_TRANSFORM_VERSION,
    }
    transform_hash = _hash_payload(transform_fields)
    time_transform_id = _stable_uuid(
        f"time-transform|{source_clock_segment_id}|{transform_hash}"
    )
    return CanonicalTimeTransformProjection(
        source_clock_segment_id=source_clock_segment_id,
        time_transform_id=time_transform_id,
        model=CANONICAL_TIME_TRANSFORM_MODEL,
        anchor_segment_time_ns=start_ns,
        anchor_session_time_us=start_source_time_us + offset_us,
        rate_num=RATE_NUM,
        rate_den=RATE_DEN,
        valid_segment_start_ns=start_ns,
        valid_segment_end_ns=end_ns,
        residual_rms_us=0.0,
        residual_p95_us=0.0,
        confidence=1.0,
        method=TIME_TRANSFORM_METHOD,
        version=TIME_TRANSFORM_VERSION,
        transform_hash=transform_hash,
    )


def _projection_logical_hash(
    *,
    fixture_id: str,
    session_id: str,
    source_id: str,
    source_stream_id: str,
    transform: CanonicalTimeTransformProjection,
    rows: tuple[SessionTimedSourceRow, ...],
    markers: tuple[SessionTimedSourceMarker, ...],
    start_session_time_us: int,
    end_session_time_us: int,
) -> str:
    payload: dict[str, object] = {
        "fixture_id": fixture_id,
        "session_id": session_id,
        "source_id": source_id,
        "source_stream_id": source_stream_id,
        "time_transform_id": transform.time_transform_id,
        "transform_hash": transform.transform_hash,
        "start_session_time_us": start_session_time_us,
        "end_session_time_us": end_session_time_us,
        "rows": [
            [
                row.source_stream_ordinal,
                row.source_time_us,
                row.session_time_us,
            ]
            for row in rows
        ],
        "markers": [
            [
                marker.marker_ordinal,
                marker.source_time_us,
                marker.session_time_us,
                marker.marker_value,
            ]
            for marker in markers
        ],
    }
    return _hash_payload(payload)


def build_session_time_projection(bundle_path: Path) -> SessionTimeProjection:
    """Map one governed fixture source clock to authoritative Session Time."""

    bundle = load_synthetic_fixture_bundle(bundle_path)
    registration = register_synthetic_fixture(bundle_path)

    if bundle.session.source_time_basis != EXPECTED_SOURCE_TIME_BASIS:
        raise SessionTimeError(
            "M1_SESSION_TIME_SOURCE_BASIS_UNSUPPORTED",
            bundle.session.source_time_basis,
        )

    context_path = bundle_path / "context" / "evaluation-context.json"
    context = _load_json(context_path)
    if context.get("fixture_id") != bundle.identity.fixture_id:
        raise SessionTimeError(
            "M1_SESSION_TIME_CONTEXT_ID_MISMATCH",
            repr(context.get("fixture_id")),
        )
    fixture_transform = _fixture_transform(context)

    source_times = tuple(parse_source_time_us(row.source_time_us) for row in bundle.rows)
    validate_source_clock_sequence(source_times)
    marker_times = tuple(
        parse_source_time_us(marker.source_time_us)
        for marker in bundle.source_markers
    )
    validate_source_clock_sequence(marker_times)

    start_source_time_us = source_times[0]
    end_source_time_us = parse_source_time_us(bundle.session.end_source_time_us)
    observed_last = max((*source_times, *marker_times), default=start_source_time_us)
    if end_source_time_us < observed_last:
        raise SessionTimeError(
            "M1_SESSION_TIME_SESSION_END_BEFORE_SOURCE",
            f"end={end_source_time_us} observed_last={observed_last}",
        )

    transform = _build_transform(
        source_stream_id=registration.source_stream_id,
        start_source_time_us=start_source_time_us,
        end_source_time_us=end_source_time_us,
        offset_us=fixture_transform.offset_us,
    )

    rows = tuple(
        SessionTimedSourceRow(
            source_stream_ordinal=index,
            source_time_us=row.source_time_us,
            session_time_us=apply_session_time_us(
                transform,
                source_time * 1000,
            ),
        )
        for index, (row, source_time) in enumerate(
            zip(bundle.rows, source_times, strict=True)
        )
    )
    markers = tuple(
        SessionTimedSourceMarker(
            marker_ordinal=index,
            source_time_us=marker.source_time_us,
            session_time_us=apply_session_time_us(
                transform,
                source_time * 1000,
            ),
            marker_value=marker.marker_value,
        )
        for index, (marker, source_time) in enumerate(
            zip(bundle.source_markers, marker_times, strict=True)
        )
    )

    start_session_time_us = apply_session_time_us(
        transform,
        start_source_time_us * 1000,
    )
    end_session_time_us = apply_session_time_us(
        transform,
        end_source_time_us * 1000,
    )
    logical_hash = _projection_logical_hash(
        fixture_id=bundle.identity.fixture_id,
        session_id=bundle.session.session_id,
        source_id=registration.source_id,
        source_stream_id=registration.source_stream_id,
        transform=transform,
        rows=rows,
        markers=markers,
        start_session_time_us=start_session_time_us,
        end_session_time_us=end_session_time_us,
    )

    return SessionTimeProjection(
        fixture_id=bundle.identity.fixture_id,
        session_id=bundle.session.session_id,
        source_id=registration.source_id,
        source_stream_id=registration.source_stream_id,
        source_time_basis=bundle.session.source_time_basis,
        start_session_time_us=start_session_time_us,
        end_session_time_us=end_session_time_us,
        transform=transform,
        rows=rows,
        markers=markers,
        logical_hash=logical_hash,
    )


def build_all_session_time_projections(
    fixture_root: Path,
) -> tuple[SessionTimeProjection, ...]:
    """Build deterministic Session Time projections for all governed fixtures."""

    return tuple(
        build_session_time_projection(fixture_root / fixture_id)
        for fixture_id in sorted(GOVERNED_FIXTURE_IDS)
    )
