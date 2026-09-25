"""TPAA ingest-layer public contracts."""

from tpaa_ingest.m2_reference_truth import (
    M2ReferenceTruthError,
    M2ReferenceTruthProjection,
    ReferenceFrameProvenance,
    ReferenceIdentity,
    ReferenceTruthRow,
    load_m2_reference_truth,
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
    "GOVERNED_FIXTURE_IDS",
    "M2ReferenceTruthError",
    "M2ReferenceTruthProjection",
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
    "load_synthetic_fixture_bundle",
]
