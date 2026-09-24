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

__all__ = [
    "ImmutableArtifactFileRef",
    "ImmutableHashRef",
    "SourceRegistryError",
    "SourceRegistryIndex",
    "SourceRegistryRegistration",
    "register_all_synthetic_fixtures",
    "register_synthetic_fixture",
]
