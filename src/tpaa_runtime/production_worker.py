"""PRCB C2 governed production domain work executed inside a fresh spawn worker."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID, uuid5

from tpaa_application.m1_publication import to_core_publication_bundle
from tpaa_generated.dto import EvaluationContextDTO
from tpaa_generated.metric_registry import P1_METRICS
from tpaa_ingest.canonical_flight_channels import CanonicalFlightRow
from tpaa_ingest.production_flight_json import validate_production_flight_document
from tpaa_metric import MetricAuthority, MetricContext, compute_representative_metrics
from tpaa_observation import (
    AircraftPublicationIdentity,
    allocate_session_release_id,
    build_session_release,
)
from tpaa_platform.worker import WorkerPayload, WorkerResult
from tpaa_storage.hashing import canonical_request_hash
from tpaa_storage.publication_bundle import CorePublicationBundle
from tpaa_world import AircraftObservedWorld, WorldEvidenceRef

PRODUCTION_P1_WORKER_SCHEMA = "TPAA_PRCB_C2_P1_WORKER_PRODUCT_V1"
P1_BUILD_COMMAND = "BUILD_P1_RELEASE"
_REPRESENTATIVE_CODES = (
    "P1-AIR-001",
    "P1-AIR-002",
    "P1-AIR-003",
    "P1-AIR-004",
    "P1-AIR-007",
)
_DATASET_NAMESPACE = UUID("daf518fe-13aa-4d23-9130-b42ac188e4cf")
_EPISODE_NAMESPACE = UUID("2f54fd82-6212-4750-a2cf-9469c6ac65ec")
_WORLD_NAMESPACE = UUID("e119738b-1527-4998-b67a-50730604ea28")
_METRIC_CONTEXT_NAMESPACE = UUID("14cf8918-af80-4afc-9ab0-02933762717c")
_EVIDENCE_NAMESPACE = UUID("de434824-1682-429b-b40d-34cd7da52204")


class ProductionWorkerError(RuntimeError):
    """Fail-closed production worker input or domain-composition error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True)
class ProductionP1WorkerProduct:
    """Serializable worker-decided P1 product; parent only persists this result."""

    schema: str
    release: CorePublicationBundle
    canonical_rows: tuple[dict[str, object], ...]
    dataset_id: str
    canonical_logical_hash: str
    world_product_id: str
    world_logical_hash: str
    metric_batch_hash: str
    source_sha256: str


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field)
    return cast(dict[str, object], value)


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field)
    return value


def _uuid(value: object, *, field: str) -> str:
    text_value = _text(value, field=field)
    try:
        parsed = UUID(text_value)
    except ValueError as exc:
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field) from exc
    if parsed.int == 0 or str(parsed) != text_value:
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field)
    return text_value


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field)
    return value


def _number(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field)
    result = float(value)
    if not math.isfinite(result):
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", field)
    return result


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _catalog(authority_root: Path) -> tuple[str, str]:
    path = authority_root / "P1_METRIC_CATALOG.json"
    try:
        data = path.read_bytes()
        raw: object = json.loads(data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProductionWorkerError(
            "PRCB_C2_METRIC_AUTHORITY_UNAVAILABLE",
            str(path),
        ) from exc
    document = _mapping(raw, field="P1_METRIC_CATALOG")
    version = _text(document.get("catalog_version"), field="catalog_version")
    return version, hashlib.sha256(data).hexdigest()


def _authorities() -> tuple[MetricAuthority, ...]:
    selected: list[MetricAuthority] = []
    for code in _REPRESENTATIVE_CODES:
        matches = [item for item in P1_METRICS if item.get("metric_code") == code]
        if len(matches) != 1:
            raise ProductionWorkerError("PRCB_C2_METRIC_AUTHORITY_DRIFT", code)
        item = matches[0]

        def required(name: str) -> str:
            return _text(item.get(name), field=f"{code}.{name}")

        semantic_version = item.get("semantic_version")
        if isinstance(semantic_version, bool) or not isinstance(semantic_version, int):
            raise ProductionWorkerError(
                "PRCB_C2_METRIC_AUTHORITY_DRIFT",
                f"{code}.semantic_version",
            )
        structured = item.get("structured_output_schema_id")
        if structured is not None and not isinstance(structured, str):
            raise ProductionWorkerError(
                "PRCB_C2_METRIC_AUTHORITY_DRIFT",
                f"{code}.structured_output_schema_id",
            )
        selected.append(
            MetricAuthority(
                metric_code=code,
                semantic_id=required("semantic_id"),
                semantic_version=semantic_version,
                subject_type=required("subject_type"),
                unit=required("unit"),
                value_kind=required("value_kind"),
                algorithm_id=required("algorithm_id"),
                algorithm_version=required("algorithm_version"),
                observation_lane=required("observation_lane"),
                publication_route=required("publication_route"),
                structured_output_schema_id=structured,
            )
        )
    return tuple(selected)


def _canonical_rows(document: dict[str, object]) -> tuple[CanonicalFlightRow, ...]:
    transform = _mapping(document.get("time_transform"), field="time_transform")
    scale = _number(transform.get("scale"), field="time_transform.scale")
    offset = _integer(transform.get("offset_us"), field="time_transform.offset_us")
    rows_raw = document.get("rows")
    if not isinstance(rows_raw, list):
        raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", "rows")
    result: list[CanonicalFlightRow] = []
    prior: int | None = None
    for ordinal, raw in enumerate(rows_raw):
        row = _mapping(raw, field=f"rows[{ordinal}]")
        source_time = _integer(row.get("source_time_us"), field="source_time_us")
        session_time = int(round(source_time * scale)) + offset
        if prior is not None and session_time <= prior:
            raise ProductionWorkerError("PRCB_C2_SESSION_TIME_INVALID", str(ordinal))
        prior = session_time

        def optional(name: str) -> float | None:
            value = row.get(name)
            return None if value is None else _number(value, field=name)

        quality = _integer(row.get("quality"), field="quality")
        if quality < 0:
            raise ProductionWorkerError("PRCB_C2_PAYLOAD_INVALID", "quality")
        result.append(
            CanonicalFlightRow(
                source_stream_ordinal=ordinal,
                session_time_us=session_time,
                body_p_rad_s=optional("p"),
                nz_g=optional("nz"),
                heading_true_rad=optional("heading"),
                tas_mps=optional("tas"),
                mach=optional("mach"),
                quality_mask=quality,
            )
        )
    if len(result) < 2:
        raise ProductionWorkerError("PRCB_C2_CANONICAL_TOO_SHORT", str(len(result)))
    return tuple(result)


def _row_dict(row: CanonicalFlightRow) -> dict[str, object]:
    return {
        "source_stream_ordinal": row.source_stream_ordinal,
        "session_time_us": row.session_time_us,
        "body_p_rad_s": row.body_p_rad_s,
        "nz_g": row.nz_g,
        "heading_true_rad": row.heading_true_rad,
        "tas_mps": row.tas_mps,
        "mach": row.mach,
        "quality_mask": row.quality_mask,
    }


def build_p1_worker_product(
    payload: Mapping[str, object],
    *,
    request_hash: str,
    authority_root: Path,
) -> ProductionP1WorkerProduct:
    """Execute Source→Canonical→World→Metric→Release entirely in worker memory."""

    body = dict(payload)
    source_json = _text(body.get("source_json"), field="source_json")
    source_bytes = source_json.encode("utf-8")
    document = validate_production_flight_document(source_bytes)
    session_id = _uuid(document.get("session_id"), field="session_id")
    aircraft_id = _uuid(document.get("aircraft_id"), field="aircraft_id")
    canonical_rows = _canonical_rows(document)
    canonical_payload = [_row_dict(row) for row in canonical_rows]
    canonical_hash = _hash(
        {
            "schema": "CANONICAL_AIRCRAFT_STATE_V1",
            "session_id": session_id,
            "aircraft_id": aircraft_id,
            "rows": canonical_payload,
        }
    )
    dataset_id = str(uuid5(_DATASET_NAMESPACE, canonical_hash))
    release_id = allocate_session_release_id(
        session_id=session_id,
        request_hash=request_hash,
    )
    episode_id = str(uuid5(_EPISODE_NAMESPACE, f"{session_id}|{canonical_hash}"))

    context_raw = _mapping(body.get("evaluation_context"), field="evaluation_context")
    context_id = _uuid(
        context_raw.get("context_id"),
        field="evaluation_context.context_id",
    )
    if _uuid(
        context_raw.get("session_id"),
        field="evaluation_context.session_id",
    ) != session_id:
        raise ProductionWorkerError("PRCB_C2_CONTEXT_SESSION_DRIFT", context_id)
    context_version = _text(
        context_raw.get("context_version"),
        field="evaluation_context.context_version",
    )
    revision_no = _integer(
        context_raw.get("revision_no"),
        field="evaluation_context.revision_no",
    )
    rule_set_version = _text(
        context_raw.get("rule_set_version"),
        field="evaluation_context.rule_set_version",
    )
    metric_profile_version = _text(
        context_raw.get("metric_profile_version"),
        field="evaluation_context.metric_profile_version",
    )
    context_status = _text(
        context_raw.get("status"),
        field="evaluation_context.status",
    )
    context_projection: EvaluationContextDTO = {
        "context_id": context_id,
        "session_id": session_id,
        "context_version": context_version,
        "revision_no": revision_no,
        "rule_set_version": rule_set_version,
        "metric_profile_version": metric_profile_version,
        "status": context_status,
    }

    start = canonical_rows[0].session_time_us
    end = canonical_rows[-1].session_time_us + 1
    context_hash = _hash(dict(context_projection))
    episode_hash = _hash(
        {
            "episode_id": episode_id,
            "session_id": session_id,
            "start_session_time_us": start,
            "end_session_time_us": end,
            "context_id": context_id,
        }
    )
    source_import = _mapping(body.get("source_import"), field="source_import")
    artifact_id = _uuid(
        source_import.get("artifact_id"),
        field="source_import.artifact_id",
    )
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    base_refs = (
        WorldEvidenceRef("EVALUATION_CONTEXT", context_id, context_hash),
        WorldEvidenceRef("CANONICAL", dataset_id, canonical_hash),
        WorldEvidenceRef("EPISODE", episode_id, episode_hash),
    )
    world_hash = _hash(
        {
            "release_id": release_id,
            "session_id": session_id,
            "episode_id": episode_id,
            "aircraft_id": aircraft_id,
            "dataset_id": dataset_id,
            "canonical_logical_hash": canonical_hash,
            "context_logical_hash": context_hash,
            "source_sha256": source_sha,
        }
    )
    world_id = str(uuid5(_WORLD_NAMESPACE, world_hash))
    world = AircraftObservedWorld(
        fixture_id=artifact_id,
        release_id=release_id,
        session_id=session_id,
        episode_id=episode_id,
        stage_id=None,
        world_product_id=world_id,
        world_kind="TRUTH",
        aircraft_id=aircraft_id,
        dataset_id=dataset_id,
        start_session_time_us=start,
        end_session_time_us=end,
        status="READY",
        coverage=1.0,
        confidence=1.0,
        reason_codes=(),
        world_version="PRCB_C2_PRODUCTION_P1_WORLD_V1",
        policy_version="PRCB-1.0:C2",
        capability_code="BASIC_CORE",
        present_capability_letters=("C", "W", "A", "M"),
        absent_capability_letters=("P", "J"),
        artifact_sha256=world_hash,
        logical_content_hash=world_hash,
        request_hash=request_hash,
        supersedes_id=None,
        canonical_rows=canonical_rows,
        stages=(),
        evidence_refs=base_refs,
    )

    profile = _mapping(body.get("metric_profile"), field="metric_profile")
    profile_id = _text(profile.get("profile_id"), field="metric_profile.profile_id")
    if profile_id != metric_profile_version:
        raise ProductionWorkerError("PRCB_C2_METRIC_PROFILE_DRIFT", profile_id)
    min_coverage = _number(
        profile.get("min_coverage"),
        field="metric_profile.min_coverage",
    )
    max_gap_us = _integer(
        profile.get("max_gap_us"),
        field="metric_profile.max_gap_us",
    )
    derivative_window_s = _number(
        profile.get("derivative_window_s"),
        field="metric_profile.derivative_window_s",
    )
    sustain_duration_s = _number(
        profile.get("sustain_duration_s"),
        field="metric_profile.sustain_duration_s",
    )
    if not 0.0 < min_coverage <= 1.0 or max_gap_us <= 0:
        raise ProductionWorkerError("PRCB_C2_METRIC_PROFILE_INVALID", profile_id)
    if derivative_window_s <= 0.0 or sustain_duration_s <= 0.0:
        raise ProductionWorkerError("PRCB_C2_METRIC_PROFILE_INVALID", profile_id)

    catalog_version, catalog_hash = _catalog(authority_root)
    refs = [*base_refs, world.world_evidence_ref]
    aggregate_hash = _hash(
        [
            {"class": ref.ref_class, "id": ref.ref_id, "hash": ref.logical_hash}
            for ref in refs
        ]
    )
    refs.append(
        WorldEvidenceRef(
            "EVIDENCE",
            str(uuid5(_EVIDENCE_NAMESPACE, aggregate_hash)),
            aggregate_hash,
        )
    )
    profile_hash = _hash(profile)
    metric_identity = _hash(
        {
            "session_id": session_id,
            "context_id": context_id,
            "aircraft_id": aircraft_id,
            "catalog_hash": catalog_hash,
            "profile_hash": profile_hash,
            "world_product_id": world_id,
        }
    )
    metric_context = MetricContext(
        metric_context_id=str(uuid5(_METRIC_CONTEXT_NAMESPACE, metric_identity)),
        fixture_id=artifact_id,
        session_id=session_id,
        context_id=context_id,
        subject_type="AIRCRAFT",
        subject_id=aircraft_id,
        catalog_id="P1_METRIC_CATALOG",
        catalog_version=catalog_version,
        catalog_sha256=catalog_hash,
        profile_id=profile_id,
        profile_sha256=profile_hash,
        min_coverage=min_coverage,
        max_gap_us=max_gap_us,
        derivative_window_s=derivative_window_s,
        sustain_duration_s=sustain_duration_s,
        authorities=_authorities(),
        input_refs=tuple(refs),
    )
    metric_batch = compute_representative_metrics(metric_context, world)

    identity_raw = _mapping(
        body.get("publication_identity"),
        field="publication_identity",
    )
    identity = AircraftPublicationIdentity(
        aircraft_id=aircraft_id,
        aircraft_model_id=_uuid(
            identity_raw.get("aircraft_model_id"),
            field="publication_identity.aircraft_model_id",
        ),
        aircraft_instance_id=_uuid(
            identity_raw.get("aircraft_instance_id"),
            field="publication_identity.aircraft_instance_id",
        ),
        subject_entity_id=_uuid(
            identity_raw.get("subject_entity_id"),
            field="publication_identity.subject_entity_id",
        ),
        capability_dimension=_text(
            identity_raw.get("capability_dimension"),
            field="publication_identity.capability_dimension",
        ),
        capability_type=_text(
            identity_raw.get("capability_type"),
            field="publication_identity.capability_type",
        ),
    )
    expected_version_token = _integer(
        body.get("expected_version_token"),
        field="expected_version_token",
    )
    if expected_version_token < 0:
        raise ProductionWorkerError(
            "PRCB_C2_PAYLOAD_INVALID",
            "expected_version_token",
        )
    parent_raw = body.get("parent_release_id")
    parent_release_id = (
        None if parent_raw is None else _uuid(parent_raw, field="parent_release_id")
    )
    if expected_version_token == 0 and parent_release_id is not None:
        raise ProductionWorkerError(
            "PRCB_C2_PARENT_RELEASE_INVALID",
            parent_release_id,
        )
    if expected_version_token > 0 and parent_release_id is None:
        raise ProductionWorkerError(
            "PRCB_C2_PARENT_RELEASE_REQUIRED",
            str(expected_version_token),
        )

    release = build_session_release(
        release_id=release_id,
        request_hash=request_hash,
        release_no=expected_version_token + 1,
        parent_release_id=parent_release_id,
        context=metric_context,
        context_version=context_version,
        context_projection=context_projection,
        world=world,
        batch=metric_batch,
        identity=identity,
    )
    return ProductionP1WorkerProduct(
        schema=PRODUCTION_P1_WORKER_SCHEMA,
        release=to_core_publication_bundle(release),
        canonical_rows=tuple(canonical_payload),
        dataset_id=dataset_id,
        canonical_logical_hash=canonical_hash,
        world_product_id=world_id,
        world_logical_hash=world_hash,
        metric_batch_hash=metric_batch.logical_hash,
        source_sha256=source_sha,
    )


def execute(payload: WorkerPayload) -> WorkerResult:
    """Governed runtime worker handler. Unknown commands fail closed."""

    if payload.command != P1_BUILD_COMMAND:
        return WorkerResult(
            job_id=payload.job_id,
            request_hash=payload.request_hash,
            command=payload.command,
            status="FAILED",
            error_code="PRCB_C2_DOMAIN_COMMAND_UNSUPPORTED",
        )
    try:
        body = _mapping(payload.domain_payload, field="domain_payload")
        authority_root = Path(_text(body.get("authority_root"), field="authority_root"))
        request_payload = _mapping(body.get("job_payload"), field="job_payload")
        expected = canonical_request_hash(
            {"job_type": payload.command, "payload": request_payload}
        )
        if expected != payload.request_hash:
            raise ProductionWorkerError(
                "PRCB_C2_REQUEST_HASH_MISMATCH",
                payload.job_id,
            )
        product = build_p1_worker_product(
            request_payload,
            request_hash=payload.request_hash,
            authority_root=authority_root,
        )
        return WorkerResult(
            job_id=payload.job_id,
            request_hash=payload.request_hash,
            command=payload.command,
            status="SUCCEEDED",
            output=(
                product.schema,
                product.release.release_id,
                product.release.manifest_hash,
                product.canonical_logical_hash,
                product.world_logical_hash,
                product.metric_batch_hash,
            ),
            domain_payload=product,
        )
    except Exception as exc:
        code = getattr(exc, "code", "PRCB_C2_DOMAIN_EXECUTION_FAILED")
        return WorkerResult(
            job_id=payload.job_id,
            request_hash=payload.request_hash,
            command=payload.command,
            status="FAILED",
            error_code=str(code),
        )
