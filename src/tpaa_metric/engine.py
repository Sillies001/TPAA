"""M1-MET-002..008 representative Metric computation and staging."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID, uuid5

from tpaa_ingest.canonical_flight_channels import CanonicalFlightRow
from tpaa_metric.context import MetricAuthority, MetricContext
from tpaa_metric.operators import (
    TimedValue,
    derivative_lls,
    quantile_hf7,
    rolling_medians,
    unwrap_angles,
)
from tpaa_world import AircraftObservedWorld, WorldEvidenceRef

METRIC_RESULT_NAMESPACE = UUID("b057bf9d-ec3d-47a7-ad98-d45b79119127")
EVIDENCE_SET_NAMESPACE = UUID("53acf930-576d-4abe-8f10-31a52277e9ee")
VALID_STATUSES = frozenset({"VALID", "N_A", "INSUFFICIENT_DATA", "INVALID", "REVIEW_REQUIRED"})


class MetricComputationError(RuntimeError):
    """Deterministic fail-closed Metric computation error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class EnvelopeChannel:
    status: str
    n: int
    minimum: float | None
    maximum: float | None
    p05: float | None
    p50: float | None
    p95: float | None


@dataclass(frozen=True)
class TasMachEnvelope:
    schema_id: str
    tas: EnvelopeChannel
    mach: EnvelopeChannel

    def as_dict(self) -> dict[str, object]:
        return {
            "tas": {
                "status": self.tas.status,
                "n": self.tas.n,
                "min_mps": self.tas.minimum,
                "max_mps": self.tas.maximum,
                "p05_mps": self.tas.p05,
                "p50_mps": self.tas.p50,
                "p95_mps": self.tas.p95,
            },
            "mach": {
                "status": self.mach.status,
                "n": self.mach.n,
                "min": self.mach.minimum,
                "max": self.mach.maximum,
                "p05": self.mach.p05,
                "p50": self.mach.p50,
                "p95": self.mach.p95,
            },
        }


@dataclass(frozen=True)
class MetricEvidence:
    evidence_set_id: str
    refs: tuple[WorldEvidenceRef, ...]
    details: tuple[tuple[str, str], ...]
    logical_hash: str


@dataclass(frozen=True)
class MetricResult:
    metric_result_id: str
    metric_code: str
    semantic_id: str
    semantic_version: int
    algorithm_id: str
    algorithm_version: str
    subject_type: str
    subject_id: str
    stage_id: str | None
    status: str
    reason_codes: tuple[str, ...]
    unit: str
    value_kind: str
    value_numeric: float | None
    value_structured: TasMachEnvelope | None
    evidence: MetricEvidence
    logical_hash: str

    def __post_init__(self) -> None:
        if self.subject_type != "AIRCRAFT":
            raise MetricComputationError("M1_METRIC_SUBJECT_NOT_APPLICABLE", self.subject_type)
        if self.status not in VALID_STATUSES:
            raise MetricComputationError("M1_METRIC_STATUS_INVALID", self.status)
        if self.status == "VALID":
            if self.value_kind == "NUMERIC":
                if self.value_numeric is None or self.value_structured is not None:
                    raise MetricComputationError("M1_METRIC_VALUE_SLOT_INVALID", self.metric_code)
                if not math.isfinite(self.value_numeric):
                    raise MetricComputationError("M1_METRIC_NUMERIC_NONFINITE", self.metric_code)
            elif self.value_kind == "STRUCTURED":
                if self.value_structured is None or self.value_numeric is not None:
                    raise MetricComputationError("M1_METRIC_VALUE_SLOT_INVALID", self.metric_code)
            else:
                raise MetricComputationError("M1_METRIC_VALUE_KIND_INVALID", self.value_kind)
        elif self.value_numeric is not None or self.value_structured is not None:
            raise MetricComputationError("M1_METRIC_NONVALID_VALUE_PRESENT", self.metric_code)


@dataclass(frozen=True)
class MetricBatch:
    metric_context_id: str
    world_product_id: str
    stage_id: str | None
    results: tuple[MetricResult, ...]
    logical_hash: str
    staging_status: str = "READY"
    database_persistence_executed: bool = False
    publication_executed: bool = False


class MetricStagingArea:
    """Atomic in-memory staging boundary; it intentionally has no publish operation."""

    def __init__(self) -> None:
        self._batches: dict[str, MetricBatch] = {}

    def stage(self, batch: MetricBatch) -> None:
        if batch.staging_status != "READY" or batch.publication_executed:
            raise MetricComputationError("M1_METRIC_BATCH_NOT_STAGEABLE", batch.logical_hash)
        if not batch.results:
            raise MetricComputationError("M1_METRIC_BATCH_EMPTY", batch.logical_hash)
        snapshot = dict(self._batches)
        snapshot[batch.logical_hash] = batch
        self._batches = snapshot

    @property
    def staged(self) -> MappingProxyType[str, MetricBatch]:
        return MappingProxyType(dict(self._batches))

    @property
    def current_published(self) -> MappingProxyType[str, MetricBatch]:
        return MappingProxyType({})


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _select_rows(
    world: AircraftObservedWorld,
    stage_id: str | None,
) -> tuple[CanonicalFlightRow, ...]:
    if stage_id is None:
        return world.canonical_rows
    stage = next((candidate for candidate in world.stages if candidate.stage_id == stage_id), None)
    if stage is None:
        raise MetricComputationError("M1_METRIC_STAGE_NOT_FOUND", stage_id)
    return tuple(
        row
        for row in world.canonical_rows
        if stage.start_session_time_us <= row.session_time_us < stage.end_session_time_us
    )


def _window_bounds(
    world: AircraftObservedWorld,
    stage_id: str | None,
) -> tuple[int, int]:
    if stage_id is None:
        return world.start_session_time_us, world.end_session_time_us
    stage = next((candidate for candidate in world.stages if candidate.stage_id == stage_id), None)
    if stage is None:
        raise MetricComputationError("M1_METRIC_STAGE_NOT_FOUND", stage_id)
    return stage.start_session_time_us, stage.end_session_time_us


def _has_excessive_gap(rows: tuple[CanonicalFlightRow, ...], max_gap_us: int) -> bool:
    times = [row.session_time_us for row in rows]
    return any(
        current - previous > max_gap_us for previous, current in zip(times, times[1:], strict=False)
    )


def _metric_evidence(
    *,
    context: MetricContext,
    authority: MetricAuthority,
    world: AircraftObservedWorld,
    stage_id: str | None,
    details: tuple[tuple[str, str], ...],
) -> MetricEvidence:
    refs = context.input_refs
    payload = {
        "metric_code": authority.metric_code,
        "metric_context_id": context.metric_context_id,
        "world_product_id": world.world_product_id,
        "stage_id": stage_id,
        "refs": [
            {"class": ref.ref_class, "id": ref.ref_id, "hash": ref.logical_hash} for ref in refs
        ],
        "details": list(details),
    }
    logical_hash = _sha256(payload)
    return MetricEvidence(
        evidence_set_id=str(uuid5(EVIDENCE_SET_NAMESPACE, logical_hash)),
        refs=refs,
        details=details,
        logical_hash=logical_hash,
    )


def _result(
    *,
    context: MetricContext,
    authority: MetricAuthority,
    world: AircraftObservedWorld,
    stage_id: str | None,
    status: str,
    reasons: tuple[str, ...] = (),
    numeric: float | None = None,
    structured: TasMachEnvelope | None = None,
    details: tuple[tuple[str, str], ...] = (),
) -> MetricResult:
    evidence = _metric_evidence(
        context=context,
        authority=authority,
        world=world,
        stage_id=stage_id,
        details=details,
    )
    value_payload = structured.as_dict() if structured is not None else numeric
    payload = {
        "metric_code": authority.metric_code,
        "semantic_id": authority.semantic_id,
        "semantic_version": authority.semantic_version,
        "algorithm_id": authority.algorithm_id,
        "algorithm_version": authority.algorithm_version,
        "subject_type": context.subject_type,
        "subject_id": context.subject_id,
        "stage_id": stage_id,
        "status": status,
        "reason_codes": list(reasons),
        "unit": authority.unit,
        "value_kind": authority.value_kind,
        "value": value_payload,
        "evidence_hash": evidence.logical_hash,
    }
    logical_hash = _sha256(payload)
    return MetricResult(
        metric_result_id=str(uuid5(METRIC_RESULT_NAMESPACE, logical_hash)),
        metric_code=authority.metric_code,
        semantic_id=authority.semantic_id,
        semantic_version=authority.semantic_version,
        algorithm_id=authority.algorithm_id,
        algorithm_version=authority.algorithm_version,
        subject_type=context.subject_type,
        subject_id=context.subject_id,
        stage_id=stage_id,
        status=status,
        reason_codes=reasons,
        unit=authority.unit,
        value_kind=authority.value_kind,
        value_numeric=numeric,
        value_structured=structured,
        evidence=evidence,
        logical_hash=logical_hash,
    )


def _finite_channel(
    rows: tuple[CanonicalFlightRow, ...],
    field: str,
) -> tuple[TimedValue, ...]:
    values: list[TimedValue] = []
    for row in rows:
        quality_mask = row.quality_mask
        value = getattr(row, field)
        if quality_mask == 0 and value is not None and math.isfinite(value):
            values.append(TimedValue(row.session_time_us, float(value)))
    return tuple(values)


def _insufficient(
    context: MetricContext,
    authority: MetricAuthority,
    world: AircraftObservedWorld,
    stage_id: str | None,
    reason: str,
) -> MetricResult:
    return _result(
        context=context,
        authority=authority,
        world=world,
        stage_id=stage_id,
        status="INSUFFICIENT_DATA",
        reasons=(reason,),
        details=(("reason", reason),),
    )


def _air_001(
    context: MetricContext,
    world: AircraftObservedWorld,
    rows: tuple[CanonicalFlightRow, ...],
    stage_id: str | None,
) -> MetricResult:
    authority = context.authority("P1-AIR-001")
    if _has_excessive_gap(rows, context.max_gap_us):
        return _insufficient(context, authority, world, stage_id, "MAX_GAP_EXCEEDED")
    values = _finite_channel(rows, "body_p_rad_s")
    coverage = len(values) / len(rows) if rows else 0.0
    if not values or coverage < context.min_coverage:
        return _insufficient(context, authority, world, stage_id, "MIN_COVERAGE_NOT_MET")
    return _result(
        context=context,
        authority=authority,
        world=world,
        stage_id=stage_id,
        status="VALID",
        numeric=max(abs(item.value) for item in values),
        details=(("coverage", repr(coverage)), ("max_gap_us", str(context.max_gap_us))),
    )


def _air_002(
    context: MetricContext,
    world: AircraftObservedWorld,
    rows: tuple[CanonicalFlightRow, ...],
    stage_id: str | None,
) -> MetricResult:
    authority = context.authority("P1-AIR-002")
    values = _finite_channel(rows, "nz_g")
    if not values:
        return _insufficient(context, authority, world, stage_id, "NZ_UNAVAILABLE")
    raw = [item.value for item in values]
    return _result(
        context=context,
        authority=authority,
        world=world,
        stage_id=stage_id,
        status="VALID",
        numeric=max(raw),
        details=(("diagnostic_min_nz_g", repr(min(raw))),),
    )


def _heading_rates(
    context: MetricContext,
    rows: tuple[CanonicalFlightRow, ...],
) -> tuple[TimedValue, ...]:
    headings = _finite_channel(rows, "heading_true_rad")
    return tuple(
        TimedValue(item.session_time_us, abs(item.value))
        for item in derivative_lls(
            unwrap_angles(headings),
            derivative_window_s=context.derivative_window_s,
            max_gap_us=context.max_gap_us,
        )
    )


def _air_003(
    context: MetricContext,
    world: AircraftObservedWorld,
    rows: tuple[CanonicalFlightRow, ...],
    stage_id: str | None,
    rates: tuple[TimedValue, ...],
) -> MetricResult:
    authority = context.authority("P1-AIR-003")
    if not rates:
        return _insufficient(context, authority, world, stage_id, "DERIVATIVE_UNAVAILABLE")
    return _result(
        context=context,
        authority=authority,
        world=world,
        stage_id=stage_id,
        status="VALID",
        numeric=max(item.value for item in rates),
        details=(("operator", "DERIVATIVE_LLS_V1"), ("rate_count", str(len(rates)))),
    )


def _air_004(
    context: MetricContext,
    world: AircraftObservedWorld,
    rows: tuple[CanonicalFlightRow, ...],
    stage_id: str | None,
    rates: tuple[TimedValue, ...],
    window_start_us: int,
    window_end_us: int,
) -> MetricResult:
    authority = context.authority("P1-AIR-004")
    if _has_excessive_gap(rows, context.max_gap_us):
        return _insufficient(context, authority, world, stage_id, "MAX_GAP_EXCEEDED")
    medians = rolling_medians(
        rates,
        duration_s=context.sustain_duration_s,
        min_coverage=context.min_coverage,
        max_gap_us=context.max_gap_us,
        window_start_us=window_start_us,
        window_end_us=window_end_us,
    )
    if not medians:
        return _insufficient(context, authority, world, stage_id, "SUSTAIN_DURATION_NOT_MET")
    best = max(medians, key=lambda item: item[0].value)
    return _result(
        context=context,
        authority=authority,
        world=world,
        stage_id=stage_id,
        status="VALID",
        numeric=best[0].value,
        details=(
            ("operator", "ROLLING_MEDIAN_V1"),
            ("supporting_dwell_start_session_time_us", str(window_start_us)),
            ("supporting_dwell_end_session_time_us", str(window_end_us)),
            ("selected_center_session_time_us", str(best[0].session_time_us)),
            ("selected_centered_window_start_session_time_us", str(best[1])),
            ("selected_centered_window_end_session_time_us", str(best[2])),
        ),
    )


def _envelope_channel(values: tuple[TimedValue, ...]) -> EnvelopeChannel:
    if not values:
        return EnvelopeChannel("INSUFFICIENT_DATA", 0, None, None, None, None, None)
    raw = [item.value for item in values]
    return EnvelopeChannel(
        status="VALID",
        n=len(raw),
        minimum=min(raw),
        maximum=max(raw),
        p05=quantile_hf7(raw, 0.05),
        p50=quantile_hf7(raw, 0.50),
        p95=quantile_hf7(raw, 0.95),
    )


def _air_007(
    context: MetricContext,
    world: AircraftObservedWorld,
    rows: tuple[CanonicalFlightRow, ...],
    stage_id: str | None,
) -> MetricResult:
    authority = context.authority("P1-AIR-007")
    envelope = TasMachEnvelope(
        schema_id="STRUCT_P1_AIR_007_V1",
        tas=_envelope_channel(_finite_channel(rows, "tas_mps")),
        mach=_envelope_channel(_finite_channel(rows, "mach")),
    )
    if envelope.tas.n == 0 and envelope.mach.n == 0:
        return _result(
            context=context,
            authority=authority,
            world=world,
            stage_id=stage_id,
            status="N_A",
            reasons=("TAS_AND_MACH_UNAVAILABLE",),
            details=(("reason", "TAS_AND_MACH_UNAVAILABLE"),),
        )
    return _result(
        context=context,
        authority=authority,
        world=world,
        stage_id=stage_id,
        status="VALID",
        structured=envelope,
        details=(("operator", "QUANTILE_HF7_V1"),),
    )


def compute_representative_metrics(
    context: MetricContext,
    world: AircraftObservedWorld,
    *,
    stage_id: str | None = None,
) -> MetricBatch:
    """Compute all five M1 representative Metrics into an unpublished batch."""

    if context.subject_type != "AIRCRAFT" or context.subject_id != world.aircraft_id:
        raise MetricComputationError("M1_METRIC_CONTEXT_SUBJECT_DRIFT", context.subject_id)
    if context.session_id != world.session_id:
        raise MetricComputationError("M1_METRIC_CONTEXT_SESSION_DRIFT", context.session_id)
    rows = _select_rows(world, stage_id)
    if not rows:
        raise MetricComputationError("M1_METRIC_WINDOW_EMPTY", repr(stage_id))
    window_start_us, window_end_us = _window_bounds(world, stage_id)
    rates = _heading_rates(context, rows)
    results = (
        _air_001(context, world, rows, stage_id),
        _air_002(context, world, rows, stage_id),
        _air_003(context, world, rows, stage_id, rates),
        _air_004(
            context,
            world,
            rows,
            stage_id,
            rates,
            window_start_us,
            window_end_us,
        ),
        _air_007(context, world, rows, stage_id),
    )
    if tuple(result.metric_code for result in results) != tuple(
        authority.metric_code for authority in context.authorities
    ):
        raise MetricComputationError("M1_METRIC_RESULT_SET_DRIFT", context.metric_context_id)
    batch_hash = _sha256(
        {
            "metric_context_id": context.metric_context_id,
            "world_product_id": world.world_product_id,
            "stage_id": stage_id,
            "result_hashes": [result.logical_hash for result in results],
        }
    )
    return MetricBatch(
        metric_context_id=context.metric_context_id,
        world_product_id=world.world_product_id,
        stage_id=stage_id,
        results=results,
        logical_hash=batch_hash,
    )
