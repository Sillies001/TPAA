"""TPAA registry-layer public contracts."""

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
    SessionTimeError,
    SessionTimeProjection,
    SessionTimedSourceMarker,
    SessionTimedSourceRow,
    apply_session_time_us,
    build_all_session_time_projections,
    build_session_time_projection,
    parse_offset_us,
    parse_source_time_us,
    validate_source_clock_sequence,
)

__all__ = [
    "ImmutableArtifactFileRef",
    "ImmutableHashRef",
    "SourceRegistryError",
    "SourceRegistryIndex",
    "SourceRegistryRegistration",
    "CanonicalTimeTransformProjection",
    "SessionTimeError",
    "SessionTimeProjection",
    "SessionTimedSourceMarker",
    "SessionTimedSourceRow",
    "apply_session_time_us",
    "build_all_session_time_projections",
    "build_session_time_projection",
    "parse_offset_us",
    "parse_source_time_us",
    "register_all_synthetic_fixtures",
    "register_synthetic_fixture",
    "validate_source_clock_sequence",
]
