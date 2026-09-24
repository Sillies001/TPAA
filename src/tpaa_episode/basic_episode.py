"""M1-WORLD-001 replay-stable Basic Flight Episode detection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid5

from tpaa_context import resolve_evaluation_context
from tpaa_ingest import load_synthetic_fixture_bundle
from tpaa_registry import build_session_time_projection, resolve_aircraft_identity

EPISODE_AUTHORITY = "M1_BASIC_FLIGHT_EPISODE_V1"
EPISODE_TYPE = "BASIC_FLIGHT"
SUBJECT_SCOPE = "AIRCRAFT"
EPISODE_NAMESPACE = UUID("19cf34fc-3f57-4ced-b94a-c5fa8131ee1a")


class BasicEpisodeError(RuntimeError):
    """Deterministic fail-closed Basic Episode error."""


@dataclass(frozen=True)
class BasicFlightEpisode:
    fixture_id: str
    session_id: str
    context_id: str
    primary_aircraft_id: str
    episode_id: str
    episode_type: str
    subject_scope: str
    start_session_time_us: int
    end_session_time_us: int
    detector_version: str
    revision_no: int
    supersedes_episode_id: str | None
    episode_status: str
    coverage: float
    confidence: float
    data_sufficiency_status: str
    logical_hash: str
    database_persistence_executed: bool = False
    stage_projection_executed: bool = False
    world_projection_executed: bool = False
    metric_logic_executed: bool = False


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def detect_basic_episode(
    bundle_path: Path,
    *,
    authority_root: Path,
) -> BasicFlightEpisode:
    """Create the single controlled Basic Flight Episode for one governed fixture."""

    bundle = load_synthetic_fixture_bundle(bundle_path)
    timed = build_session_time_projection(bundle_path)
    context = resolve_evaluation_context(
        bundle_path,
        authority_root=authority_root,
    )
    aircraft = resolve_aircraft_identity(bundle_path)

    if timed.session_id != bundle.session.session_id or context.session_id != timed.session_id:
        raise BasicEpisodeError("M1_EPISODE_SESSION_DRIFT")
    if context.stage_profile_id != "BASIC_FLIGHT_V1":
        raise BasicEpisodeError("M1_EPISODE_STAGE_PROFILE_DRIFT")
    if timed.start_session_time_us >= timed.end_session_time_us:
        raise BasicEpisodeError("M1_EPISODE_INTERVAL_INVALID")

    identity = {
        "session_id": timed.session_id,
        "context_id": context.context_id,
        "primary_aircraft_id": aircraft.aircraft_id,
        "episode_type": EPISODE_TYPE,
        "start_session_time_us": timed.start_session_time_us,
        "end_session_time_us": timed.end_session_time_us,
        "detector_version": EPISODE_AUTHORITY,
    }
    identity_bytes = _canonical_bytes(identity)
    episode_id = str(uuid5(EPISODE_NAMESPACE, identity_bytes.decode("ascii")))
    logical_payload = {
        **identity,
        "episode_id": episode_id,
        "subject_scope": SUBJECT_SCOPE,
        "revision_no": 1,
        "supersedes_episode_id": None,
        "episode_status": "VALID",
        "coverage": 1.0,
        "confidence": 1.0,
        "data_sufficiency_status": "SUFFICIENT",
    }
    logical_hash = hashlib.sha256(_canonical_bytes(logical_payload)).hexdigest()
    return BasicFlightEpisode(
        fixture_id=bundle.identity.fixture_id,
        session_id=timed.session_id,
        context_id=context.context_id,
        primary_aircraft_id=aircraft.aircraft_id,
        episode_id=episode_id,
        episode_type=EPISODE_TYPE,
        subject_scope=SUBJECT_SCOPE,
        start_session_time_us=timed.start_session_time_us,
        end_session_time_us=timed.end_session_time_us,
        detector_version=EPISODE_AUTHORITY,
        revision_no=1,
        supersedes_episode_id=None,
        episode_status="VALID",
        coverage=1.0,
        confidence=1.0,
        data_sufficiency_status="SUFFICIENT",
        logical_hash=logical_hash,
    )
