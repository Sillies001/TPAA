from __future__ import annotations

import pytest

from tpaa_ingest import (
    FROZEN_SOURCE_FAMILIES,
    ProductionSourceAdapterError,
    SourceAdapterDescriptor,
    SourceAdapterRegistry,
    SourceArtifactEnvelope,
    SourceFamily,
)


def _descriptors() -> tuple[SourceAdapterDescriptor, ...]:
    return tuple(
        SourceAdapterDescriptor(
            adapter_id=f"builtin-{family.value.lower().replace('_', '-')}",
            adapter_version="1.0.0",
            source_family=family,
            media_types=(f"application/x-tpaa-{family.value.lower()}",),
            external_decoder=family is SourceFamily.FLIGHT,
        )
        for family in SourceFamily
    )


def test_registry_covers_exact_frozen_six_source_families() -> None:
    registry = SourceAdapterRegistry(_descriptors())

    assert FROZEN_SOURCE_FAMILIES == frozenset(
        {
            SourceFamily.FLIGHT,
            SourceFamily.MISSION_AVIONICS,
            SourceFamily.TDL,
            SourceFamily.RANGE_ACMI,
            SourceFamily.SCENARIO,
            SourceFamily.AUDIO_VIDEO,
        }
    )
    assert len(registry.inventory()) == 6
    assert {item.source_family for item in registry.inventory()} == FROZEN_SOURCE_FAMILIES


def test_external_decoder_is_metadata_not_core_dependency() -> None:
    registry = SourceAdapterRegistry(_descriptors())
    descriptor = registry.exact("builtin-flight", "1.0.0")

    assert descriptor.source_family is SourceFamily.FLIGHT
    assert descriptor.external_decoder is True


def test_registry_validates_exact_adapter_family_media_and_byte_identity() -> None:
    registry = SourceAdapterRegistry(_descriptors())
    envelope = SourceArtifactEnvelope(
        source_family=SourceFamily.TDL,
        adapter_id="builtin-tdl",
        adapter_version="1.0.0",
        source_ref="source://fixture/tdl.bin",
        artifact_sha256="a" * 64,
        size_bytes=128,
        media_type="application/x-tpaa-tdl",
        classification_label="TEST",
    )

    registry.validate_envelope(envelope)

    with pytest.raises(
        ProductionSourceAdapterError,
        match="B3_SOURCE_ADAPTER_MEDIA_TYPE_UNSUPPORTED",
    ):
        registry.validate_envelope(
            SourceArtifactEnvelope(
                source_family=envelope.source_family,
                adapter_id=envelope.adapter_id,
                adapter_version=envelope.adapter_version,
                source_ref=envelope.source_ref,
                artifact_sha256=envelope.artifact_sha256,
                size_bytes=envelope.size_bytes,
                media_type="application/octet-stream",
                classification_label=envelope.classification_label,
            )
        )


def test_registry_rejects_conflicting_redefinition_and_bad_hash() -> None:
    registry = SourceAdapterRegistry(_descriptors())
    with pytest.raises(
        ProductionSourceAdapterError,
        match="B3_SOURCE_ADAPTER_IMMUTABLE_CONFLICT",
    ):
        registry.register(
            SourceAdapterDescriptor(
                adapter_id="builtin-flight",
                adapter_version="1.0.0",
                source_family=SourceFamily.SCENARIO,
                media_types=("application/x-tpaa-scenario",),
            )
        )

    with pytest.raises(
        ProductionSourceAdapterError,
        match="B3_SOURCE_ARTIFACT_HASH_INVALID",
    ):
        registry.validate_envelope(
            SourceArtifactEnvelope(
                source_family=SourceFamily.FLIGHT,
                adapter_id="builtin-flight",
                adapter_version="1.0.0",
                source_ref="source://fixture/flight.bin",
                artifact_sha256="NOT-A-SHA",
                size_bytes=1,
                media_type="application/x-tpaa-flight",
            )
        )
