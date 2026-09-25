"""TPAA ingest-layer public contracts."""

from tpaa_ingest.m2_reference_truth import (
    M2ReferenceTruthError,
    M2ReferenceTruthProjection,
    ReferenceFrameProvenance,
    ReferenceIdentity,
    ReferenceTruthRow,
    load_m2_reference_truth,
)
from tpaa_ingest.m2_time_alignment import (
    ClockAlignmentSample,
    ClockSegment,
    InterpolationInput,
    LatencyInput,
    M2TimeAlignmentError,
    M2TimeAlignmentProjection,
    NavTimeUncertaintyInput,
    load_m2_time_alignment,
)
from tpaa_ingest.source_adapter import (
    GOVERNED_FIXTURE_IDS,
    SourceArtifactIdentity,
    SyntheticAircraftSource,
    SyntheticSessionSource,
    SyntheticSourceAdapterError,
    SyntheticSourceBundle,
    SyntheticSourceMarker,
    SyntheticSourceRow,
    load_synthetic_fixture_bundle,
)

__all__ = [
    "ClockAlignmentSample",
    "ClockSegment",
    "GOVERNED_FIXTURE_IDS",
    "InterpolationInput",
    "LatencyInput",
    "M2ReferenceTruthError",
    "M2ReferenceTruthProjection",
    "M2TimeAlignmentError",
    "M2TimeAlignmentProjection",
    "NavTimeUncertaintyInput",
    "ReferenceFrameProvenance",
    "ReferenceIdentity",
    "ReferenceTruthRow",
    "SourceArtifactIdentity",
    "SyntheticAircraftSource",
    "SyntheticSessionSource",
    "SyntheticSourceAdapterError",
    "SyntheticSourceBundle",
    "SyntheticSourceMarker",
    "SyntheticSourceRow",
    "load_m2_reference_truth",
    "load_m2_time_alignment",
    "load_synthetic_fixture_bundle",
]
