"""PIQB B3 governed production source-adapter contracts and registry."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class SourceFamily(StrEnum):
    """Frozen PIQB production source families."""

    FLIGHT = "FLIGHT"
    MISSION_AVIONICS = "MISSION_AVIONICS"
    TDL = "TDL"
    RANGE_ACMI = "RANGE_ACMI"
    SCENARIO = "SCENARIO"
    AUDIO_VIDEO = "AUDIO_VIDEO"


FROZEN_SOURCE_FAMILIES = frozenset(SourceFamily)


class ProductionSourceAdapterError(RuntimeError):
    """Fail-closed production source-adapter contract error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True)
class SourceAdapterDescriptor:
    """Immutable adapter identity registered at the ingest boundary."""

    adapter_id: str
    adapter_version: str
    source_family: SourceFamily
    media_types: tuple[str, ...]
    external_decoder: bool = False


@dataclass(frozen=True)
class SourceArtifactEnvelope:
    """Byte-identity envelope produced before business projection starts."""

    source_family: SourceFamily
    adapter_id: str
    adapter_version: str
    source_ref: str
    artifact_sha256: str
    size_bytes: int
    media_type: str
    classification_label: str | None = None


class SourceAdapter(Protocol):
    """Platform-facing adapter port; implementations may live outside TPAA Core."""

    @property
    def descriptor(self) -> SourceAdapterDescriptor: ...

    def inspect(
        self,
        *,
        source_ref: str,
        data: bytes,
        media_type: str,
        classification_label: str | None = None,
    ) -> SourceArtifactEnvelope: ...


def _require_token(value: str, *, field: str) -> str:
    if not value or value.strip() != value:
        raise ProductionSourceAdapterError(
            "B3_SOURCE_ADAPTER_DESCRIPTOR_INVALID",
            field,
        )
    return value


def _validate_descriptor(descriptor: SourceAdapterDescriptor) -> None:
    _require_token(descriptor.adapter_id, field="adapter_id")
    _require_token(descriptor.adapter_version, field="adapter_version")
    if descriptor.source_family not in FROZEN_SOURCE_FAMILIES:
        raise ProductionSourceAdapterError(
            "B3_SOURCE_FAMILY_NOT_GOVERNED",
            str(descriptor.source_family),
        )
    if not descriptor.media_types:
        raise ProductionSourceAdapterError(
            "B3_SOURCE_ADAPTER_DESCRIPTOR_INVALID",
            "media_types",
        )
    if len(set(descriptor.media_types)) != len(descriptor.media_types):
        raise ProductionSourceAdapterError(
            "B3_SOURCE_ADAPTER_DESCRIPTOR_INVALID",
            "duplicate media_types",
        )
    for media_type in descriptor.media_types:
        _require_token(media_type, field="media_type")


class SourceAdapterRegistry:
    """Exact adapter registry with no format guessing or implicit decoder fallback."""

    def __init__(
        self,
        descriptors: tuple[SourceAdapterDescriptor, ...] = (),
    ) -> None:
        self._descriptors: dict[tuple[str, str], SourceAdapterDescriptor] = {}
        for descriptor in descriptors:
            self.register(descriptor)

    def register(self, descriptor: SourceAdapterDescriptor) -> None:
        _validate_descriptor(descriptor)
        key = (descriptor.adapter_id, descriptor.adapter_version)
        current = self._descriptors.get(key)
        if current is None:
            self._descriptors[key] = descriptor
            return
        if current != descriptor:
            raise ProductionSourceAdapterError(
                "B3_SOURCE_ADAPTER_IMMUTABLE_CONFLICT",
                f"{descriptor.adapter_id}:{descriptor.adapter_version}",
            )

    def exact(self, adapter_id: str, adapter_version: str) -> SourceAdapterDescriptor:
        descriptor = self._descriptors.get((adapter_id, adapter_version))
        if descriptor is None:
            raise ProductionSourceAdapterError(
                "B3_SOURCE_ADAPTER_NOT_REGISTERED",
                f"{adapter_id}:{adapter_version}",
            )
        return descriptor

    def for_family(self, family: SourceFamily) -> tuple[SourceAdapterDescriptor, ...]:
        return tuple(
            sorted(
                (
                    descriptor
                    for descriptor in self._descriptors.values()
                    if descriptor.source_family is family
                ),
                key=lambda item: (item.adapter_id, item.adapter_version),
            )
        )

    def require_family(
        self,
        family: SourceFamily,
    ) -> tuple[SourceAdapterDescriptor, ...]:
        """Resolve an explicitly configured family or fail without fallback."""

        descriptors = self.for_family(family)
        if not descriptors:
            raise ProductionSourceAdapterError("UNSUPPORTED_ADAPTER", family.value)
        return descriptors

    def inventory(self) -> tuple[SourceAdapterDescriptor, ...]:
        return tuple(
            sorted(
                self._descriptors.values(),
                key=lambda item: (
                    item.source_family.value,
                    item.adapter_id,
                    item.adapter_version,
                ),
            )
        )

    def validate_envelope(self, envelope: SourceArtifactEnvelope) -> None:
        descriptor = self.exact(envelope.adapter_id, envelope.adapter_version)
        if envelope.source_family is not descriptor.source_family:
            raise ProductionSourceAdapterError(
                "B3_SOURCE_ADAPTER_FAMILY_MISMATCH",
                envelope.source_family.value,
            )
        if envelope.media_type not in descriptor.media_types:
            raise ProductionSourceAdapterError(
                "B3_SOURCE_ADAPTER_MEDIA_TYPE_UNSUPPORTED",
                envelope.media_type,
            )
        _require_token(envelope.source_ref, field="source_ref")
        if not _SHA256_RE.fullmatch(envelope.artifact_sha256):
            raise ProductionSourceAdapterError(
                "B3_SOURCE_ARTIFACT_HASH_INVALID",
                envelope.artifact_sha256,
            )
        if envelope.size_bytes < 0:
            raise ProductionSourceAdapterError(
                "B3_SOURCE_ARTIFACT_SIZE_INVALID",
                str(envelope.size_bytes),
            )
        if envelope.classification_label is not None:
            _require_token(
                envelope.classification_label,
                field="classification_label",
            )
