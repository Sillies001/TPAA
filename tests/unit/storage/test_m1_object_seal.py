from __future__ import annotations

import pytest

from tpaa_storage.object_seal import LocalSealedObjectFlow, ObjectSealError
from tpaa_storage.object_store import LocalObjectStore


def test_staging_can_be_cleaned_without_creating_sealed_object(tmp_path) -> None:
    store = LocalObjectStore(tmp_path)
    flow = LocalSealedObjectFlow(store)
    sealed_uri = "tpaa-object://release/objects/example.json"
    staged = flow.stage(sealed_uri=sealed_uri, data=b'{"a":1}', operation_id="cancelled")

    assert store.physical_path(staged.staging.logical_uri).is_file()
    assert not store.physical_path(sealed_uri).exists()
    assert flow.cleanup(staged) is True
    assert not store.physical_path(staged.staging.logical_uri).exists()
    assert not store.physical_path(sealed_uri).exists()


def test_seal_verifies_bytes_and_removes_staging_object(tmp_path) -> None:
    store = LocalObjectStore(tmp_path)
    flow = LocalSealedObjectFlow(store)
    sealed_uri = "tpaa-object://release/objects/example.json"
    staged = flow.stage(sealed_uri=sealed_uri, data=b'{"a":1}', operation_id="success")

    sealed = flow.seal(staged)

    assert store.verify(sealed)
    assert store.read_bytes(sealed_uri) == b'{"a":1}'
    assert not store.physical_path(staged.staging.logical_uri).exists()


def test_sealed_logical_uri_cannot_be_replaced_with_different_bytes(tmp_path) -> None:
    store = LocalObjectStore(tmp_path)
    flow = LocalSealedObjectFlow(store)
    uri = "tpaa-object://release/objects/example.json"
    store.put_bytes(uri, b"old")
    staged = flow.stage(sealed_uri=uri, data=b"new", operation_id="conflict")

    with pytest.raises(ObjectSealError):
        flow.seal(staged)
