"""Governed immutable references for production Source ingress artifacts."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit
from uuid import UUID

from tpaa_storage import ObjectStore, ObjectStoreError

SOURCE_INGRESS_NAMESPACE = "source-ingress"
MAX_SOURCE_ARTIFACT_BYTES = 64 * 1024 * 1024
_REFERENCE_FIELDS = frozenset({"logical_uri", "artifact_sha256", "byte_size"})


class SourceArtifactError(RuntimeError):
    """Fail-closed Source ingress reference or object error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class SourceArtifactReference:
    """JSON-safe immutable identity for one managed Source artifact."""

    logical_uri: str
    artifact_sha256: str
    byte_size: int

    def as_payload(self) -> dict[str, object]:
        return {
            "logical_uri": self.logical_uri,
            "artifact_sha256": self.artifact_sha256,
            "byte_size": self.byte_size,
        }


def source_artifact_uri(artifact_id: str) -> str:
    """Allocate the sole governed URI for a Source artifact identity."""

    try:
        parsed = UUID(artifact_id)
    except ValueError as exc:
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_ID_INVALID",
            artifact_id,
        ) from exc
    if parsed.int == 0 or str(parsed) != artifact_id:
        raise SourceArtifactError("SOURCE_ARTIFACT_ID_INVALID", artifact_id)
    return f"tpaa-object://{SOURCE_INGRESS_NAMESPACE}/{artifact_id}/source.json"


def _validate_size(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SourceArtifactError("SOURCE_ARTIFACT_REFERENCE_INVALID", "byte_size")
    if value <= 0 or value > MAX_SOURCE_ARTIFACT_BYTES:
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_SIZE_INVALID",
            str(value),
        )
    return value


def _validate_hash(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_REFERENCE_INVALID",
            "artifact_sha256",
        )
    return value


def parse_source_artifact_reference(
    value: object,
    *,
    artifact_id: str,
) -> SourceArtifactReference:
    """Parse a strict reference and bind it to the provenance artifact ID."""

    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise SourceArtifactError("SOURCE_ARTIFACT_REFERENCE_INVALID", "mapping")
    raw = dict(cast(Mapping[str, object], value))
    if set(raw) != _REFERENCE_FIELDS:
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_REFERENCE_INVALID",
            "fields",
        )
    logical_uri = raw.get("logical_uri")
    if not isinstance(logical_uri, str):
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_REFERENCE_INVALID",
            "logical_uri",
        )
    expected_uri = source_artifact_uri(artifact_id)
    if logical_uri != expected_uri:
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_URI_IDENTITY_DRIFT",
            logical_uri,
        )
    parsed_uri = urlsplit(logical_uri)
    if parsed_uri.scheme != "tpaa-object" or parsed_uri.netloc != SOURCE_INGRESS_NAMESPACE:
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_URI_UNMANAGED",
            logical_uri,
        )
    return SourceArtifactReference(
        logical_uri=logical_uri,
        artifact_sha256=_validate_hash(raw.get("artifact_sha256")),
        byte_size=_validate_size(raw.get("byte_size")),
    )


def stage_source_artifact(
    store: ObjectStore,
    *,
    artifact_id: str,
    data: bytes,
) -> SourceArtifactReference:
    """Write one bounded JSON artifact under its immutable managed identity."""

    _validate_size(len(data))
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_ENCODING_INVALID",
            artifact_id,
        ) from exc
    logical_uri = source_artifact_uri(artifact_id)
    digest = hashlib.sha256(data).hexdigest()
    try:
        stored = store.put_bytes_immutable(logical_uri, data)
    except ObjectStoreError as exc:
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_IMMUTABILITY_CONFLICT",
            artifact_id,
        ) from exc
    if (
        stored.artifact_sha256 != digest
        or stored.byte_size != len(data)
        or not store.verify(stored)
    ):
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_WRITE_VERIFY_FAILED",
            artifact_id,
        )
    return SourceArtifactReference(
        logical_uri=stored.logical_uri,
        artifact_sha256=stored.artifact_sha256,
        byte_size=stored.byte_size,
    )


def stage_source_artifact_file(
    store: ObjectStore,
    *,
    artifact_id: str,
    source_file: Path,
) -> SourceArtifactReference:
    """Stage one regular file after a pre-read size bound check."""

    if not source_file.is_file():
        raise SourceArtifactError("SOURCE_ARTIFACT_FILE_INVALID", str(source_file))
    size = source_file.stat().st_size
    _validate_size(size)
    return stage_source_artifact(
        store,
        artifact_id=artifact_id,
        data=source_file.read_bytes(),
    )


def stage_inline_source_documents(
    store: ObjectStore,
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Client-side migration helper: stage inline JSON and return references."""

    result = dict(payload)
    raw_documents = payload.get("source_documents")
    if raw_documents is None:
        documents: Sequence[object] = (payload,)
        nested = False
    elif isinstance(raw_documents, Sequence) and not isinstance(raw_documents, (str, bytes)):
        documents = raw_documents
        nested = True
        result.pop("source_json", None)
    else:
        raise SourceArtifactError("SOURCE_ARTIFACT_REFERENCE_INVALID", "source_documents")

    staged: list[dict[str, object]] = []
    for index, raw in enumerate(documents):
        if not isinstance(raw, Mapping) or not all(isinstance(key, str) for key in raw):
            raise SourceArtifactError(
                "SOURCE_ARTIFACT_REFERENCE_INVALID",
                f"source_documents[{index}]",
            )
        item = dict(cast(Mapping[str, object], raw))
        source_json = item.pop("source_json", None)
        if not isinstance(source_json, str):
            raise SourceArtifactError(
                "SOURCE_ARTIFACT_INLINE_REQUIRED_FOR_STAGING",
                f"source_documents[{index}]",
            )
        metadata_value = item.get("source_import")
        if not isinstance(metadata_value, Mapping):
            raise SourceArtifactError(
                "SOURCE_ARTIFACT_REFERENCE_INVALID",
                f"source_documents[{index}].source_import",
            )
        metadata = dict(cast(Mapping[str, object], metadata_value))
        artifact_id = metadata.get("artifact_id")
        if not isinstance(artifact_id, str):
            raise SourceArtifactError(
                "SOURCE_ARTIFACT_REFERENCE_INVALID",
                f"source_documents[{index}].artifact_id",
            )
        reference = stage_source_artifact(
            store,
            artifact_id=artifact_id,
            data=source_json.encode("utf-8"),
        )
        metadata["uri_kind"] = "MANAGED"
        metadata["source_ref"] = reference.logical_uri
        item["source_import"] = metadata
        item["source_artifact"] = reference.as_payload()
        staged.append(item)

    if nested:
        result["source_documents"] = staged
    else:
        result = staged[0]
    return result


def resolve_source_artifact(
    store: ObjectStore,
    document: Mapping[str, object],
) -> tuple[SourceArtifactReference, bytes]:
    """Resolve one production document from a managed reference, never inline data."""

    if "source_json" in document:
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_INLINE_FORBIDDEN",
            "source_json",
        )
    metadata = document.get("source_import")
    if not isinstance(metadata, Mapping):
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_REFERENCE_INVALID",
            "source_import",
        )
    artifact_id = metadata.get("artifact_id")
    if not isinstance(artifact_id, str):
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_REFERENCE_INVALID",
            "artifact_id",
        )
    reference = parse_source_artifact_reference(
        document.get("source_artifact"),
        artifact_id=artifact_id,
    )
    if metadata.get("uri_kind") != "MANAGED":
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_URI_KIND_INVALID",
            str(metadata.get("uri_kind")),
        )
    if metadata.get("source_ref") != reference.logical_uri:
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_SOURCE_REF_DRIFT",
            reference.logical_uri,
        )
    try:
        data = store.read_bytes(reference.logical_uri)
    except ObjectStoreError as exc:
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_UNAVAILABLE",
            reference.logical_uri,
        ) from exc
    if len(data) != reference.byte_size:
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_SIZE_MISMATCH",
            reference.logical_uri,
        )
    if hashlib.sha256(data).hexdigest() != reference.artifact_sha256:
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_HASH_MISMATCH",
            reference.logical_uri,
        )
    return reference, data


def materialize_source_documents(
    store: ObjectStore,
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Build a transient worker payload from immutable Source references."""

    result = dict(payload)
    raw_documents = payload.get("source_documents")
    if raw_documents is None:
        documents: Sequence[object] = (payload,)
        nested = False
    elif "source_json" in payload:
        raise SourceArtifactError(
            "SOURCE_ARTIFACT_INLINE_FORBIDDEN",
            "source_json",
        )
    elif isinstance(raw_documents, Sequence) and not isinstance(raw_documents, (str, bytes)):
        documents = raw_documents
        nested = True
    else:
        raise SourceArtifactError("SOURCE_ARTIFACT_REFERENCE_INVALID", "source_documents")

    materialized: list[dict[str, object]] = []
    for index, raw in enumerate(documents):
        if not isinstance(raw, Mapping) or not all(isinstance(key, str) for key in raw):
            raise SourceArtifactError(
                "SOURCE_ARTIFACT_REFERENCE_INVALID",
                f"source_documents[{index}]",
            )
        item = dict(cast(Mapping[str, object], raw))
        _reference, data = resolve_source_artifact(store, item)
        try:
            item["source_json"] = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceArtifactError(
                "SOURCE_ARTIFACT_ENCODING_INVALID",
                f"source_documents[{index}]",
            ) from exc
        materialized.append(item)

    if nested:
        result["source_documents"] = materialized
    else:
        result.update(materialized[0])
    return result


def source_reference_payload(
    materialized_payload: Mapping[str, object],
) -> dict[str, object]:
    """Reconstruct the hash-authoritative reference request inside a worker."""

    result = dict(materialized_payload)
    raw_documents = materialized_payload.get("source_documents")
    if raw_documents is None:
        if "source_artifact" not in result:
            raise SourceArtifactError(
                "SOURCE_ARTIFACT_REFERENCE_INVALID",
                "source_artifact",
            )
        result.pop("source_json", None)
        return result
    if not isinstance(raw_documents, Sequence) or isinstance(raw_documents, (str, bytes)):
        raise SourceArtifactError("SOURCE_ARTIFACT_REFERENCE_INVALID", "source_documents")
    documents: list[dict[str, object]] = []
    for index, raw in enumerate(raw_documents):
        if not isinstance(raw, Mapping) or "source_artifact" not in raw:
            raise SourceArtifactError(
                "SOURCE_ARTIFACT_REFERENCE_INVALID",
                f"source_documents[{index}].source_artifact",
            )
        item = dict(cast(Mapping[str, object], raw))
        item.pop("source_json", None)
        documents.append(item)
    result.pop("source_json", None)
    result["source_documents"] = documents
    return result
