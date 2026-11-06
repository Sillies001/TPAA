from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_runtime import (
    SourceArtifactError,
    materialize_source_documents,
    resolve_source_artifact,
    stage_source_artifact,
)
from tpaa_storage import LocalObjectStore

ARTIFACT_ID = "d6000000-0000-4000-8000-000000000001"


def _document(reference: dict[str, object]) -> dict[str, object]:
    return {
        "source_artifact": reference,
        "source_import": {
            "artifact_id": ARTIFACT_ID,
            "source_ref": reference["logical_uri"],
            "uri_kind": "MANAGED",
        },
    }


def test_source_artifact_round_trip_and_worker_materialization(
    tmp_path: Path,
) -> None:
    store = LocalObjectStore(tmp_path / "objects")
    data = b'{"schema":"TEST"}'
    reference = stage_source_artifact(
        store,
        artifact_id=ARTIFACT_ID,
        data=data,
    )

    resolved_reference, resolved = resolve_source_artifact(
        store,
        _document(reference.as_payload()),
    )
    assert resolved_reference == reference
    assert resolved == data

    materialized = materialize_source_documents(
        store,
        {"source_documents": [_document(reference.as_payload())]},
    )
    documents = materialized["source_documents"]
    assert isinstance(documents, list)
    assert documents[0]["source_json"] == data.decode("utf-8")


def test_source_artifact_identity_is_immutable(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path / "objects")
    stage_source_artifact(
        store,
        artifact_id=ARTIFACT_ID,
        data=b'{"version":1}',
    )

    with pytest.raises(
        SourceArtifactError,
        match="SOURCE_ARTIFACT_IMMUTABILITY_CONFLICT",
    ):
        stage_source_artifact(
            store,
            artifact_id=ARTIFACT_ID,
            data=b'{"version":2}',
        )


def test_source_artifact_rejects_inline_and_hash_drift(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path / "objects")
    reference = stage_source_artifact(
        store,
        artifact_id=ARTIFACT_ID,
        data=b'{"schema":"TEST"}',
    ).as_payload()
    inline = _document(reference)
    inline["source_json"] = "{}"
    with pytest.raises(
        SourceArtifactError,
        match="SOURCE_ARTIFACT_INLINE_FORBIDDEN",
    ):
        resolve_source_artifact(store, inline)

    drifted = dict(reference)
    drifted["artifact_sha256"] = "0" * 64
    with pytest.raises(
        SourceArtifactError,
        match="SOURCE_ARTIFACT_HASH_MISMATCH",
    ):
        resolve_source_artifact(store, _document(drifted))


def test_source_artifact_rejects_unmanaged_or_extra_reference_fields(
    tmp_path: Path,
) -> None:
    store = LocalObjectStore(tmp_path / "objects")
    reference = stage_source_artifact(
        store,
        artifact_id=ARTIFACT_ID,
        data=b'{"schema":"TEST"}',
    ).as_payload()
    reference["logical_uri"] = f"file:///tmp/{ARTIFACT_ID}.json"
    with pytest.raises(
        SourceArtifactError,
        match="SOURCE_ARTIFACT_URI_IDENTITY_DRIFT",
    ):
        resolve_source_artifact(store, _document(reference))

    reference = stage_source_artifact(
        store,
        artifact_id=ARTIFACT_ID,
        data=b'{"schema":"TEST"}',
    ).as_payload()
    reference["path"] = "untrusted.json"
    with pytest.raises(
        SourceArtifactError,
        match="SOURCE_ARTIFACT_REFERENCE_INVALID",
    ):
        resolve_source_artifact(store, _document(reference))


def test_source_artifact_rejects_provenance_uri_drift(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path / "objects")
    reference = stage_source_artifact(
        store,
        artifact_id=ARTIFACT_ID,
        data=b'{"schema":"TEST"}',
    ).as_payload()
    document = _document(reference)
    metadata = document["source_import"]
    assert isinstance(metadata, dict)
    metadata["source_ref"] = "external-file://untrusted/source.json"
    with pytest.raises(
        SourceArtifactError,
        match="SOURCE_ARTIFACT_SOURCE_REF_DRIFT",
    ):
        resolve_source_artifact(store, document)
