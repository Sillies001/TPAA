"""M1-DATA-005 physical-to-Canonical aircraft flight-channel projection.

This module is the controlled M1 normalization boundary for
CANONICAL_AIRCRAFT_STATE_V1. It consumes already-governed source rows plus
authoritative Session Time and aircraft identity inputs. It does not bind an
Evaluation Context, persist datasets, project Stage/World products, or execute
Metric logic.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from types import MappingProxyType

from tpaa_ingest.source_adapter import SyntheticSourceBundle

CANONICAL_AIRCRAFT_STATE_AUTHORITY = "CANONICAL_AIRCRAFT_STATE_V1"
CANONICAL_FLIGHT_CHANNELS = (
    "body_p_rad_s",
    "nz_g",
    "heading_true_rad",
    "tas_mps",
    "mach",
    "session_time_us",
    "quality_mask",
)
PHYSICAL_CHANNEL_BY_CANONICAL = MappingProxyType(
    {
        "body_p_rad_s": "p",
        "nz_g": "nz",
        "heading_true_rad": "heading",
        "tas_mps": "tas",
        "mach": "mach",
        "quality_mask": "quality",
    }
)


class CanonicalFlightChannelError(RuntimeError):
    """Deterministic fail-closed Canonical flight-channel projection error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class CanonicalFlightRow:
    """One normalized aircraft-state sample in authoritative Session Time."""

    source_stream_ordinal: int
    session_time_us: int
    body_p_rad_s: float | None
    nz_g: float | None
    heading_true_rad: float | None
    tas_mps: float | None
    mach: float | None
    quality_mask: int


@dataclass(frozen=True)
class CanonicalFlightProjection:
    """In-memory M1 Canonical aircraft-state projection for one frozen fixture."""

    fixture_id: str
    fixture_version: str
    session_id: str
    aircraft_id: str
    authority_id: str
    mapping_version: str
    input_sha256: str
    source_sha256: str
    context_sha256: str
    channel_names: tuple[str, ...]
    rows: tuple[CanonicalFlightRow, ...]
    logical_hash: str
    database_persistence_executed: bool = False
    evaluation_context_binding_executed: bool = False
    stage_projection_executed: bool = False
    world_projection_executed: bool = False
    metric_logic_executed: bool = False


def _optional_finite_float(value: object, *, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CanonicalFlightChannelError(
            "M1_CANONICAL_CHANNEL_VALUE_INVALID",
            f"{field} must be finite number or null",
        )
    normalized = float(value)
    if not math.isfinite(normalized):
        raise CanonicalFlightChannelError(
            "M1_CANONICAL_CHANNEL_VALUE_INVALID",
            f"{field} must be finite number or null",
        )
    return normalized


def _quality_mask(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CanonicalFlightChannelError(
            "M1_CANONICAL_QUALITY_MASK_INVALID",
            "quality must be a non-negative integer",
        )
    return value


def _logical_hash(
    *,
    bundle: SyntheticSourceBundle,
    aircraft_id: str,
    rows: tuple[CanonicalFlightRow, ...],
) -> str:
    payload = {
        "authority_id": CANONICAL_AIRCRAFT_STATE_AUTHORITY,
        "fixture_id": bundle.identity.fixture_id,
        "fixture_version": bundle.identity.fixture_version,
        "session_id": bundle.session.session_id,
        "aircraft_id": aircraft_id,
        "mapping_version": bundle.mapping_version,
        "input_sha256": bundle.identity.input_sha256,
        "source_sha256": bundle.identity.source_sha256,
        "context_sha256": bundle.identity.context_sha256,
        "channel_names": list(CANONICAL_FLIGHT_CHANNELS),
        "rows": [
            {
                "source_stream_ordinal": row.source_stream_ordinal,
                "session_time_us": row.session_time_us,
                "body_p_rad_s": row.body_p_rad_s,
                "nz_g": row.nz_g,
                "heading_true_rad": row.heading_true_rad,
                "tas_mps": row.tas_mps,
                "mach": row.mach,
                "quality_mask": row.quality_mask,
            }
            for row in rows
        ],
    }
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def project_canonical_flight_channels(
    bundle: SyntheticSourceBundle,
    *,
    aircraft_id: str,
    session_time_us: Sequence[int],
) -> CanonicalFlightProjection:
    """Project exact governed M1 source channels onto CANONICAL_AIRCRAFT_STATE_V1."""

    if not aircraft_id:
        raise CanonicalFlightChannelError(
            "M1_CANONICAL_AIRCRAFT_ID_MISSING",
            "aircraft_id is required",
        )
    if len(session_time_us) != len(bundle.rows):
        raise CanonicalFlightChannelError(
            "M1_CANONICAL_SESSION_TIME_COUNT_MISMATCH",
            f"rows={len(bundle.rows)} session_times={len(session_time_us)}",
        )

    rows: list[CanonicalFlightRow] = []
    previous_time: int | None = None
    for ordinal, (source_row, session_time) in enumerate(
        zip(bundle.rows, session_time_us, strict=True)
    ):
        if isinstance(session_time, bool) or not isinstance(session_time, int):
            raise CanonicalFlightChannelError(
                "M1_CANONICAL_SESSION_TIME_INVALID",
                f"ordinal={ordinal} value={session_time!r}",
            )
        if previous_time is not None and session_time <= previous_time:
            raise CanonicalFlightChannelError(
                "M1_CANONICAL_SESSION_TIME_NOT_STRICTLY_INCREASING",
                f"ordinal={ordinal} previous={previous_time} current={session_time}",
            )
        previous_time = session_time
        values = source_row.values
        rows.append(
            CanonicalFlightRow(
                source_stream_ordinal=ordinal,
                session_time_us=session_time,
                body_p_rad_s=_optional_finite_float(
                    values["p"],
                    field=f"rows[{ordinal}].p",
                ),
                nz_g=_optional_finite_float(
                    values["nz"],
                    field=f"rows[{ordinal}].nz",
                ),
                heading_true_rad=_optional_finite_float(
                    values["heading"],
                    field=f"rows[{ordinal}].heading",
                ),
                tas_mps=_optional_finite_float(
                    values["tas"],
                    field=f"rows[{ordinal}].tas",
                ),
                mach=_optional_finite_float(
                    values["mach"],
                    field=f"rows[{ordinal}].mach",
                ),
                quality_mask=_quality_mask(values["quality"]),
            )
        )

    projected_rows = tuple(rows)
    return CanonicalFlightProjection(
        fixture_id=bundle.identity.fixture_id,
        fixture_version=bundle.identity.fixture_version,
        session_id=bundle.session.session_id,
        aircraft_id=aircraft_id,
        authority_id=CANONICAL_AIRCRAFT_STATE_AUTHORITY,
        mapping_version=bundle.mapping_version,
        input_sha256=bundle.identity.input_sha256,
        source_sha256=bundle.identity.source_sha256,
        context_sha256=bundle.identity.context_sha256,
        channel_names=CANONICAL_FLIGHT_CHANNELS,
        rows=projected_rows,
        logical_hash=_logical_hash(
            bundle=bundle,
            aircraft_id=aircraft_id,
            rows=projected_rows,
        ),
    )
