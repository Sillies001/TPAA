"""M1-DATA-004 deterministic Aircraft entity resolution.

The controlled M1 fixture carries the governed business identity as
`aircraft_id`. Source-local aircraft aliases are preserved only as lineage
evidence. This module validates and resolves that governed identity without
inventing identifiers from filenames, row order, callsigns, aliases, wall
clock, or host-specific inputs.

It deliberately stops before aircraft-instance creation, Canonical flight
channel projection, Evaluation Context binding, Stage, World, or Metric
execution owned by later M1 tasks.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from tpaa_ingest import GOVERNED_FIXTURE_IDS, load_synthetic_fixture_bundle

from .source_registration import register_synthetic_fixture

EXPECTED_AIRCRAFT_ID_FIELD = "aircraft_id"
SOURCE_ALIAS_ROLE = "LINEAGE_ONLY"
RESOLUTION_METHOD = "GOVERNED_FIXTURE_AIRCRAFT_ID"
RESOLUTION_VERSION = "1.0.0"


class AircraftIdentityError(RuntimeError):
    """Deterministic fail-closed aircraft identity resolution error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class AircraftIdentityResolution:
    """Resolved governed aircraft identity plus immutable replay lineage."""

    fixture_id: str
    fixture_version: str
    session_id: str
    aircraft_id: str
    identity_field: str
    source_aircraft_key: str
    source_alias_role: str
    source_id: str
    source_stream_id: str
    source_artifact_ref: str
    source_artifact_sha256: str
    context_artifact_ref: str
    context_artifact_sha256: str
    input_sha256: str
    resolution_method: str
    resolution_version: str
    replay_basis_sha256: str
    logical_hash: str
    master_aircraft_persistence_executed: bool = False
    aircraft_instance_projection_executed: bool = False
    canonical_flight_channel_projection_executed: bool = False
    evaluation_context_binding_executed: bool = False
    stage_projection_executed: bool = False
    metric_logic_executed: bool = False


def parse_governed_aircraft_id(value: str) -> str:
    """Validate the frozen fixture aircraft_id as canonical non-nil UUID text."""

    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise AircraftIdentityError(
            "M1_AIRCRAFT_IDENTITY_UUID_INVALID",
            repr(value),
        ) from exc
    canonical = str(parsed)
    if parsed.int == 0 or canonical != value:
        raise AircraftIdentityError(
            "M1_AIRCRAFT_IDENTITY_UUID_INVALID",
            repr(value),
        )
    return canonical


def _hash_payload(payload: dict[str, object]) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def resolve_aircraft_identity(bundle_path: Path) -> AircraftIdentityResolution:
    """Resolve one fixture to its governed aircraft_id and replay lineage."""

    bundle = load_synthetic_fixture_bundle(bundle_path)
    registration = register_synthetic_fixture(bundle_path)
    aircraft_id = parse_governed_aircraft_id(bundle.aircraft.aircraft_id)

    replay_basis = {
        "fixture_id": bundle.identity.fixture_id,
        "fixture_version": bundle.identity.fixture_version,
        "input_sha256": bundle.identity.input_sha256,
        "source_artifact_sha256": registration.source_artifact.sha256,
        "context_artifact_sha256": registration.context_artifact.sha256,
        "session_id": bundle.session.session_id,
        "aircraft_id": aircraft_id,
        "identity_field": EXPECTED_AIRCRAFT_ID_FIELD,
        "resolution_method": RESOLUTION_METHOD,
        "resolution_version": RESOLUTION_VERSION,
    }
    replay_basis_sha256 = _hash_payload(replay_basis)
    logical_hash = _hash_payload(
        {
            **replay_basis,
            "replay_basis_sha256": replay_basis_sha256,
            "source_aircraft_key": bundle.aircraft.source_aircraft_key,
            "source_alias_role": SOURCE_ALIAS_ROLE,
            "source_id": registration.source_id,
            "source_stream_id": registration.source_stream_id,
            "source_artifact_ref": registration.source_artifact.logical_ref,
            "context_artifact_ref": registration.context_artifact.logical_ref,
        }
    )

    return AircraftIdentityResolution(
        fixture_id=bundle.identity.fixture_id,
        fixture_version=bundle.identity.fixture_version,
        session_id=bundle.session.session_id,
        aircraft_id=aircraft_id,
        identity_field=EXPECTED_AIRCRAFT_ID_FIELD,
        source_aircraft_key=bundle.aircraft.source_aircraft_key,
        source_alias_role=SOURCE_ALIAS_ROLE,
        source_id=registration.source_id,
        source_stream_id=registration.source_stream_id,
        source_artifact_ref=registration.source_artifact.logical_ref,
        source_artifact_sha256=registration.source_artifact.sha256,
        context_artifact_ref=registration.context_artifact.logical_ref,
        context_artifact_sha256=registration.context_artifact.sha256,
        input_sha256=bundle.identity.input_sha256,
        resolution_method=RESOLUTION_METHOD,
        resolution_version=RESOLUTION_VERSION,
        replay_basis_sha256=replay_basis_sha256,
        logical_hash=logical_hash,
    )


def resolve_all_aircraft_identities(
    fixture_root: Path,
) -> tuple[AircraftIdentityResolution, ...]:
    """Resolve all governed fixtures and enforce the M1 single-aircraft profile."""

    resolutions = tuple(
        resolve_aircraft_identity(fixture_root / fixture_id)
        for fixture_id in sorted(GOVERNED_FIXTURE_IDS)
    )
    aircraft_ids = {item.aircraft_id for item in resolutions}
    if len(aircraft_ids) != 1:
        raise AircraftIdentityError(
            "M1_AIRCRAFT_IDENTITY_SINGLE_AIRCRAFT_CONFLICT",
            repr(sorted(aircraft_ids)),
        )
    return resolutions
