"""TPAA ingest-layer public contracts."""

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
    "SourceArtifactIdentity",
    "SyntheticAircraftSource",
    "SyntheticSessionSource",
    "SyntheticSourceAdapterError",
    "SyntheticSourceBundle",
    "SyntheticSourceMarker",
    "SyntheticSourceRow",
    "load_synthetic_fixture_bundle",
]
