"""Governed production interchange adapters for non-FLIGHT source families.

Native/vendor decoders stay outside TPAA Core.  A Gateway may emit this exact
versioned interchange only after it has resolved the external format.  TPAA
still records immutable source bytes, adapter identity, family and profile
provenance before any World or Metric projection is allowed.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, cast
from uuid import UUID

from .production_source import (
    ProductionSourceAdapterError,
    SourceAdapterDescriptor,
    SourceArtifactEnvelope,
    SourceFamily,
)

PRODUCTION_INTERCHANGE_SCHEMA: Final = "TPAA_PRODUCTION_INTERCHANGE_SOURCE_V1"
PRODUCTION_INTERCHANGE_SCHEMA_VERSION: Final = "1.0.0"
PRODUCTION_INTERCHANGE_ADAPTER_VERSION: Final = "1.0.0"

_INTERCHANGE_IDENTITY: Final = {
    SourceFamily.MISSION_AVIONICS: (
        "tpaa-production-mission-avionics-json",
        "application/vnd.tpaa.mission-avionics+json",
    ),
    SourceFamily.TDL: (
        "tpaa-production-tdl-json",
        "application/vnd.tpaa.tdl+json",
    ),
    SourceFamily.RANGE_ACMI: (
        "tpaa-production-range-acmi-json",
        "application/vnd.tpaa.range-acmi+json",
    ),
    SourceFamily.SCENARIO: (
        "tpaa-production-scenario-json",
        "application/vnd.tpaa.scenario+json",
    ),
    SourceFamily.AUDIO_VIDEO: (
        "tpaa-production-audio-video-json",
        "application/vnd.tpaa.audio-video+json",
    ),
}
PRODUCTION_INTERCHANGE_FAMILIES: Final = frozenset(_INTERCHANGE_IDENTITY)


@dataclass(frozen=True, slots=True)
class GovernedInterchangeDocument:
    source_family: SourceFamily
    session_id: str
    profile_id: str
    profile_version: str
    profile_hash: str
    knowledge_time_utc: str
    payload: Mapping[str, object]


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ProductionSourceAdapterError(
            "ED2_INTERCHANGE_DOCUMENT_INVALID",
            field,
        )
    return value


def _uuid(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    try:
        parsed = UUID(text)
    except ValueError as exc:
        raise ProductionSourceAdapterError(
            "ED2_INTERCHANGE_DOCUMENT_INVALID",
            field,
        ) from exc
    if parsed.int == 0 or str(parsed) != text:
        raise ProductionSourceAdapterError(
            "ED2_INTERCHANGE_DOCUMENT_INVALID",
            field,
        )
    return text


def _hash64(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ProductionSourceAdapterError(
            "ED2_INTERCHANGE_DOCUMENT_INVALID",
            field,
        )
    return text


def validate_production_interchange_document(
    data: bytes,
    *,
    expected_family: SourceFamily | None = None,
) -> GovernedInterchangeDocument:
    """Validate an exact governed interchange document without format guessing."""

    try:
        raw: object = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProductionSourceAdapterError(
            "ED2_INTERCHANGE_DOCUMENT_INVALID",
            "json",
        ) from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ProductionSourceAdapterError(
            "ED2_INTERCHANGE_DOCUMENT_INVALID",
            "root",
        )
    document = cast(dict[str, object], raw)
    required = {
        "schema",
        "schema_version",
        "source_family",
        "session_id",
        "profile",
        "knowledge_time_utc",
        "payload",
    }
    if set(document) != required:
        raise ProductionSourceAdapterError(
            "ED2_INTERCHANGE_DOCUMENT_INVALID",
            "root_fields",
        )
    if (
        document["schema"] != PRODUCTION_INTERCHANGE_SCHEMA
        or document["schema_version"] != PRODUCTION_INTERCHANGE_SCHEMA_VERSION
    ):
        raise ProductionSourceAdapterError(
            "ED2_INTERCHANGE_SCHEMA_UNSUPPORTED",
            repr((document["schema"], document["schema_version"])),
        )
    family_text = _text(document["source_family"], field="source_family")
    try:
        family = SourceFamily(family_text)
    except ValueError as exc:
        raise ProductionSourceAdapterError(
            "ED2_INTERCHANGE_FAMILY_UNSUPPORTED",
            family_text,
        ) from exc
    if family not in PRODUCTION_INTERCHANGE_FAMILIES:
        raise ProductionSourceAdapterError(
            "ED2_INTERCHANGE_FAMILY_UNSUPPORTED",
            family.value,
        )
    if expected_family is not None and family is not expected_family:
        raise ProductionSourceAdapterError(
            "ED2_INTERCHANGE_FAMILY_MISMATCH",
            f"expected={expected_family.value};actual={family.value}",
        )

    profile_raw = document["profile"]
    if not isinstance(profile_raw, dict) or not all(
        isinstance(key, str) for key in profile_raw
    ):
        raise ProductionSourceAdapterError(
            "ED2_INTERCHANGE_DOCUMENT_INVALID",
            "profile",
        )
    profile = cast(dict[str, object], profile_raw)
    if set(profile) != {"profile_id", "profile_version", "profile_hash"}:
        raise ProductionSourceAdapterError(
            "ED2_INTERCHANGE_DOCUMENT_INVALID",
            "profile_fields",
        )
    payload = document["payload"]
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) for key in payload
    ):
        raise ProductionSourceAdapterError(
            "ED2_INTERCHANGE_DOCUMENT_INVALID",
            "payload",
        )
    return GovernedInterchangeDocument(
        source_family=family,
        session_id=_uuid(document["session_id"], field="session_id"),
        profile_id=_text(profile["profile_id"], field="profile.profile_id"),
        profile_version=_text(
            profile["profile_version"],
            field="profile.profile_version",
        ),
        profile_hash=_hash64(
            profile["profile_hash"],
            field="profile.profile_hash",
        ),
        knowledge_time_utc=_text(
            document["knowledge_time_utc"],
            field="knowledge_time_utc",
        ),
        payload=cast(dict[str, object], payload),
    )


def production_interchange_descriptors() -> tuple[SourceAdapterDescriptor, ...]:
    return tuple(
        SourceAdapterDescriptor(
            adapter_id=_INTERCHANGE_IDENTITY[family][0],
            adapter_version=PRODUCTION_INTERCHANGE_ADAPTER_VERSION,
            source_family=family,
            media_types=(_INTERCHANGE_IDENTITY[family][1],),
            external_decoder=True,
        )
        for family in sorted(
            PRODUCTION_INTERCHANGE_FAMILIES,
            key=lambda item: item.value,
        )
    )


def descriptor_for_interchange_family(
    family: SourceFamily,
) -> SourceAdapterDescriptor:
    if family not in PRODUCTION_INTERCHANGE_FAMILIES:
        raise ProductionSourceAdapterError(
            "ED2_INTERCHANGE_FAMILY_UNSUPPORTED",
            family.value,
        )
    adapter_id, media_type = _INTERCHANGE_IDENTITY[family]
    return SourceAdapterDescriptor(
        adapter_id=adapter_id,
        adapter_version=PRODUCTION_INTERCHANGE_ADAPTER_VERSION,
        source_family=family,
        media_types=(media_type,),
        external_decoder=True,
    )


class ProductionInterchangeJsonAdapter:
    """Exact adapter for one non-FLIGHT governed interchange family."""

    def __init__(self, family: SourceFamily) -> None:
        self._descriptor = descriptor_for_interchange_family(family)

    @property
    def descriptor(self) -> SourceAdapterDescriptor:
        return self._descriptor

    def inspect(
        self,
        *,
        source_ref: str,
        data: bytes,
        media_type: str,
        classification_label: str | None = None,
    ) -> SourceArtifactEnvelope:
        if media_type not in self._descriptor.media_types:
            raise ProductionSourceAdapterError(
                "B3_SOURCE_ADAPTER_MEDIA_TYPE_UNSUPPORTED",
                media_type,
            )
        validate_production_interchange_document(
            data,
            expected_family=self._descriptor.source_family,
        )
        if not source_ref or source_ref.strip() != source_ref:
            raise ProductionSourceAdapterError(
                "B3_SOURCE_ADAPTER_DESCRIPTOR_INVALID",
                "source_ref",
            )
        return SourceArtifactEnvelope(
            source_family=self._descriptor.source_family,
            adapter_id=self._descriptor.adapter_id,
            adapter_version=self._descriptor.adapter_version,
            source_ref=source_ref,
            artifact_sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            media_type=media_type,
            classification_label=classification_label,
        )
