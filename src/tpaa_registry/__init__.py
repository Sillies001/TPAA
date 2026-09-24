"""TPAA registry-layer public contracts."""

from .aircraft_identity import (
    AircraftIdentityError,
    AircraftIdentityResolution,
    parse_governed_aircraft_id,
    resolve_aircraft_identity,
    resolve_all_aircraft_identities,
)
from .source_registration import (
    ImmutableArtifactFileRef,
    ImmutableHashRef,
    SourceRegistryError,
    SourceRegistryIndex,
    SourceRegistryRegistration,
    register_all_synthetic_fixtures,
    register_synthetic_fixture,
)
from .time_alignment import (
    CanonicalTimeTransformProjection,
    SessionTimedSourceMarker,
    SessionTimedSourceRow,
    SessionTimeError,
    SessionTimeProjection,
    apply_session_time_us,
    build_all_session_time_projections,
    build_session_time_projection,
    parse_offset_us,
    parse_source_time_us,
    validate_source_clock_sequence,
)

__all__ = [
    "AircraftIdentityError",
    "AircraftIdentityResolution",
    "CanonicalTimeTransformProjection",
    "ImmutableArtifactFileRef",
    "ImmutableHashRef",
    "SessionTimeError",
    "SessionTimeProjection",
    "SessionTimedSourceMarker",
    "SessionTimedSourceRow",
    "SourceRegistryError",
    "SourceRegistryIndex",
    "SourceRegistryRegistration",
    "apply_session_time_us",
    "build_all_session_time_projections",
    "build_session_time_projection",
    "parse_governed_aircraft_id",
    "parse_offset_us",
    "parse_source_time_us",
    "register_all_synthetic_fixtures",
    "register_synthetic_fixture",
    "resolve_aircraft_identity",
    "resolve_all_aircraft_identities",
    "validate_source_clock_sequence",
]
