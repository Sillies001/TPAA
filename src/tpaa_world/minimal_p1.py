"""M1-WORLD-004/006/007 minimal P1 aircraft-observed World product."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid5

from tpaa_context import resolve_evaluation_context
from tpaa_episode import QualifiedBasicFlightStage, project_basic_flight_stage_quality
from tpaa_ingest import load_synthetic_fixture_bundle
from tpaa_ingest.canonical_flight_channels import (
    CanonicalFlightRow,
    project_canonical_flight_channels,
)
from tpaa_registry import build_session_time_projection, resolve_aircraft_identity

WORLD_VERSION = "M1_P1_AIRCRAFT_OBSERVED_WORLD_V1"
WORLD_POLICY_VERSION = "WORLD_CAPABILITY_REGISTRY:1.0.0"
WORLD_CAPABILITY_CODE = "BASIC_CORE"
WORLD_KIND = "TRUTH"
WORLD_STATUS = "READY"
WORLD_NAMESPACE = UUID("41daf87a-fde0-4f9b-8eb1-0a6f6d983d6f")
DATASET_NAMESPACE = UUID("45daac66-81dd-4efd-8840-9497a44ed360")
PRESENT_CAPABILITY_LETTERS = ("C", "W", "A", "M")
ABSENT_CAPABILITY_LETTERS = ("P", "J")


class WorldProjectionError(RuntimeError):
    """Deterministic fail-closed World projection error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class WorldEvidenceRef:
    """Immutable upstream reference consumable by Metric Evidence."""

    ref_class: str
    ref_id: str
    logical_hash: str

    def __post_init__(self) -> None:
        if not self.ref_class or not self.ref_id:
            raise WorldProjectionError("M1_WORLD_EVIDENCE_REF_INVALID", repr(self))
        if len(self.logical_hash) != 64:
            raise WorldProjectionError("M1_WORLD_EVIDENCE_HASH_INVALID", self.logical_hash)


@dataclass(frozen=True)
class AircraftObservedWorld:
    """In-memory World manifest plus exact governed aircraft-state content."""

    fixture_id: str
    release_id: str
    session_id: str
    episode_id: str
    stage_id: None
    world_product_id: str
    world_kind: str
    aircraft_id: str
    dataset_id: str
    start_session_time_us: int
    end_session_time_us: int
    status: str
    coverage: float
    confidence: float
    reason_codes: tuple[str, ...]
    world_version: str
    policy_version: str
    capability_code: str
    present_capability_letters: tuple[str, ...]
    absent_capability_letters: tuple[str, ...]
    artifact_sha256: str
    logical_content_hash: str
    request_hash: str
    supersedes_id: None
    canonical_rows: tuple[CanonicalFlightRow, ...]
    stages: tuple[QualifiedBasicFlightStage, ...]
    evidence_refs: tuple[WorldEvidenceRef, ...]
    database_persistence_executed: bool = False
    observation_projection_executed: bool = False
    release_publication_executed: bool = False
    metric_logic_executed: bool = False

    @property
    def world_evidence_ref(self) -> WorldEvidenceRef:
        """Return the non-circular self reference used by downstream Metrics."""

        return WorldEvidenceRef("WORLD", self.world_product_id, self.logical_content_hash)


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


def _canonical_uuid(value: str, *, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise WorldProjectionError("M1_WORLD_UUID_INVALID", f"{field}={value!r}") from exc
    canonical = str(parsed)
    if parsed.int == 0 or canonical != value:
        raise WorldProjectionError("M1_WORLD_UUID_INVALID", f"{field}={value!r}")
    return canonical


def _stage_hash(stage: QualifiedBasicFlightStage) -> str:
    return _sha256(
        {
            "episode_id": stage.episode_id,
            "stage_id": stage.stage_id,
            "stage_type": stage.stage_type,
            "stage_order": stage.stage_order,
            "start_session_time_us": stage.start_session_time_us,
            "end_session_time_us": stage.end_session_time_us,
            "detection_method": stage.detection_method,
            "stage_status": stage.stage_status,
            "coverage": stage.coverage,
            "confidence": stage.confidence,
            "detector_version": stage.detector_version,
            "supersedes_stage_id": stage.supersedes_stage_id,
        }
    )


def _row_payload(row: CanonicalFlightRow) -> dict[str, object]:
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


def project_minimal_p1_world(
    bundle_path: Path,
    *,
    authority_root: Path,
    release_id: str,
) -> AircraftObservedWorld:
    """Build one replay-stable, cross-platform minimal aircraft World product."""

    canonical_release_id = _canonical_uuid(release_id, field="release_id")
    bundle = load_synthetic_fixture_bundle(bundle_path)
    timed = build_session_time_projection(bundle_path)
    aircraft = resolve_aircraft_identity(bundle_path)
    context = resolve_evaluation_context(bundle_path, authority_root=authority_root)
    stage_projection = project_basic_flight_stage_quality(
        bundle_path,
        authority_root=authority_root,
    )
    canonical = project_canonical_flight_channels(
        bundle,
        aircraft_id=aircraft.aircraft_id,
        session_time_us=tuple(row.session_time_us for row in timed.rows),
    )
    if not canonical.rows:
        raise WorldProjectionError("M1_WORLD_CANONICAL_EMPTY", bundle.identity.fixture_id)
    if context.session_id != canonical.session_id:
        raise WorldProjectionError(
            "M1_WORLD_CONTEXT_SESSION_DRIFT",
            f"context={context.session_id} canonical={canonical.session_id}",
        )
    if stage_projection.episode_id != stage_projection.stages[0].episode_id:
        raise WorldProjectionError("M1_WORLD_STAGE_EPISODE_DRIFT", stage_projection.episode_id)

    dataset_id = str(uuid5(DATASET_NAMESPACE, canonical.logical_hash))
    rows_payload = [_row_payload(row) for row in canonical.rows]
    stages_payload = [
        {
            "stage_id": stage.stage_id,
            "stage_type": stage.stage_type,
            "stage_order": stage.stage_order,
            "start_session_time_us": stage.start_session_time_us,
            "end_session_time_us": stage.end_session_time_us,
            "stage_status": stage.stage_status,
            "coverage": stage.coverage,
            "confidence": stage.confidence,
            "detector_version": stage.detector_version,
        }
        for stage in stage_projection.stages
    ]
    logical_payload = {
        "session_id": canonical.session_id,
        "episode_id": stage_projection.episode_id,
        "stage_id": None,
        "world_kind": WORLD_KIND,
        "aircraft_id": aircraft.aircraft_id,
        "dataset_id": dataset_id,
        "start_session_time_us": timed.start_session_time_us,
        "end_session_time_us": timed.end_session_time_us,
        "world_version": WORLD_VERSION,
        "policy_version": WORLD_POLICY_VERSION,
        "capability_code": WORLD_CAPABILITY_CODE,
        "present_capability_letters": list(PRESENT_CAPABILITY_LETTERS),
        "absent_capability_letters": list(ABSENT_CAPABILITY_LETTERS),
        "context_logical_hash": context.logical_hash,
        "canonical_logical_hash": canonical.logical_hash,
        "rows": rows_payload,
        "stages": stages_payload,
    }
    logical_content_hash = _sha256(logical_payload)
    request_hash = _sha256(
        {
            "release_id": canonical_release_id,
            "fixture_id": bundle.identity.fixture_id,
            "input_sha256": bundle.identity.input_sha256,
            "logical_content_hash": logical_content_hash,
            "world_version": WORLD_VERSION,
            "policy_version": WORLD_POLICY_VERSION,
        }
    )
    identity = {
        "release_id": canonical_release_id,
        "session_id": canonical.session_id,
        "episode_id": stage_projection.episode_id,
        "stage_id": None,
        "world_kind": WORLD_KIND,
        "aircraft_id": aircraft.aircraft_id,
        "dataset_id": dataset_id,
        "start_session_time_us": timed.start_session_time_us,
        "end_session_time_us": timed.end_session_time_us,
        "world_version": WORLD_VERSION,
        "policy_version": WORLD_POLICY_VERSION,
        "logical_content_hash": logical_content_hash,
        "request_hash": request_hash,
    }
    world_product_id = str(uuid5(WORLD_NAMESPACE, _canonical_bytes(identity).decode("ascii")))

    refs = [
        WorldEvidenceRef("EVALUATION_CONTEXT", context.context_id, context.logical_hash),
        WorldEvidenceRef("CANONICAL", dataset_id, canonical.logical_hash),
        WorldEvidenceRef(
            "EPISODE",
            stage_projection.episode_id,
            _sha256(
                {
                    "episode_id": stage_projection.episode_id,
                    "session_id": canonical.session_id,
                    "start_session_time_us": timed.start_session_time_us,
                    "end_session_time_us": timed.end_session_time_us,
                }
            ),
        ),
    ]
    refs.extend(
        WorldEvidenceRef("STAGE", stage.stage_id, _stage_hash(stage))
        for stage in stage_projection.stages
    )
    return AircraftObservedWorld(
        fixture_id=bundle.identity.fixture_id,
        release_id=canonical_release_id,
        session_id=canonical.session_id,
        episode_id=stage_projection.episode_id,
        stage_id=None,
        world_product_id=world_product_id,
        world_kind=WORLD_KIND,
        aircraft_id=aircraft.aircraft_id,
        dataset_id=dataset_id,
        start_session_time_us=timed.start_session_time_us,
        end_session_time_us=timed.end_session_time_us,
        status=WORLD_STATUS,
        coverage=1.0,
        confidence=1.0,
        reason_codes=(),
        world_version=WORLD_VERSION,
        policy_version=WORLD_POLICY_VERSION,
        capability_code=WORLD_CAPABILITY_CODE,
        present_capability_letters=PRESENT_CAPABILITY_LETTERS,
        absent_capability_letters=ABSENT_CAPABILITY_LETTERS,
        artifact_sha256=logical_content_hash,
        logical_content_hash=logical_content_hash,
        request_hash=request_hash,
        supersedes_id=None,
        canonical_rows=canonical.rows,
        stages=stage_projection.stages,
        evidence_refs=tuple(refs),
    )
