from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_storage.hashing import (
    HashInputError,
    artifact_byte_hash,
    canonical_request_hash,
    logical_content_hash,
)
from tpaa_storage.object_store import LocalObjectStore, ObjectStoreError


def test_hash_primitives_are_distinct_and_deterministic() -> None:
    request_a = {"command": "Import", "session_time_us": "9007199254740993.125", "x": 1}
    request_b = {"x": 1, "session_time_us": "9007199254740993.125", "command": "Import"}
    logical = {"kind": "RESULT", "value": "12.5"}

    assert canonical_request_hash(request_a) == canonical_request_hash(request_b)
    assert logical_content_hash(logical) == logical_content_hash({"value": "12.5", "kind": "RESULT"})
    assert artifact_byte_hash(b"abc") != artifact_byte_hash(b"abc\n")
    assert canonical_request_hash(request_a) != logical_content_hash(logical)


def test_hash_contract_rejects_float_and_requires_decimal_string_semantics() -> None:
    with pytest.raises(HashInputError):
        canonical_request_hash({"session_time_us": 1.25})


def test_logical_uri_is_independent_of_physical_root(tmp_path) -> None:
    uri = "tpaa-object://fixture/M0/测试/payload.bin"
    left = LocalObjectStore(tmp_path / "left")
    right = LocalObjectStore(tmp_path / "right")
    data = b"same-logical-object"

    left_ref = left.put_bytes(uri, data)
    right_ref = right.put_bytes(uri, data)

    assert left_ref == right_ref
    assert left.verify(left_ref)
    assert right.verify(right_ref)
    assert left.physical_path(uri) != right.physical_path(uri)
    assert str(tmp_path) not in left_ref.logical_uri


def test_parquet_scheme_is_layout_only_and_unsafe_uri_is_rejected(tmp_path) -> None:
    store = LocalObjectStore(tmp_path / "objects")
    ref = store.put_bytes("tpaa-parquet://fixture/table/part-000.parquet", b"PAR1")
    assert ref.logical_uri.startswith("tpaa-parquet://")
    assert store.read_bytes(ref.logical_uri) == b"PAR1"

    with pytest.raises(ObjectStoreError):
        store.physical_path("file:///tmp/not-logical")
    with pytest.raises(ObjectStoreError):
        store.physical_path("tpaa-object://fixture/../escape")
