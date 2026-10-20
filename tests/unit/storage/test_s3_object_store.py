from __future__ import annotations

from io import BytesIO
from typing import Any

import pytest

from tpaa_storage import ObjectStore, ObjectStoreError, S3ObjectStore


class FakeS3Error(RuntimeError):
    def __init__(self, code: str) -> None:
        self.response = {"Error": {"Code": code}}
        super().__init__(code)


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.bucket_available = True

    def head_bucket(self, *, Bucket: str) -> None:
        if not self.bucket_available or Bucket != "tpaa-integration":
            raise FakeS3Error("404")

    def put_object(self, **parameters: Any) -> None:
        identity = (str(parameters["Bucket"]), str(parameters["Key"]))
        if parameters.get("IfNoneMatch") == "*" and identity in self.objects:
            raise FakeS3Error("PreconditionFailed")
        self.objects[identity] = bytes(parameters["Body"])

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        try:
            data = self.objects[(Bucket, Key)]
        except KeyError as exc:
            raise FakeS3Error("NoSuchKey") from exc
        return {"Body": BytesIO(data)}

    def list_objects_v2(self, **parameters: object) -> dict[str, object]:
        bucket = str(parameters["Bucket"])
        prefix = str(parameters["Prefix"])
        keys = sorted(
            key
            for candidate_bucket, key in self.objects
            if candidate_bucket == bucket and key.startswith(prefix)
        )
        return {
            "Contents": [{"Key": key} for key in keys],
            "IsTruncated": False,
        }

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.objects.pop((Bucket, Key), None)


def _store(client: FakeS3Client) -> S3ObjectStore:
    return S3ObjectStore(
        bucket="tpaa-integration",
        prefix="candidate/objects",
        client=client,
    )


def test_s3_store_satisfies_backend_neutral_protocol_and_round_trips() -> None:
    client = FakeS3Client()
    store = _store(client)
    assert isinstance(store, ObjectStore)
    store.ensure_ready()
    first = store.put_bytes("tpaa-object://reports/one.json", b"one")
    second = store.put_bytes("tpaa-object://reports/two.json", b"two")
    assert store.read_bytes(first.logical_uri) == b"one"
    assert store.verify(first) is True
    assert store.list_objects("tpaa-object://reports") == (first, second)


def test_s3_immutable_put_allows_exact_replay_and_rejects_overwrite() -> None:
    store = _store(FakeS3Client())
    logical_uri = "tpaa-object://source-ingress/artifact/source.json"
    first = store.put_bytes_immutable(logical_uri, b"same")
    assert store.put_bytes_immutable(logical_uri, b"same") == first
    with pytest.raises(ObjectStoreError, match="immutable object already exists"):
        store.put_bytes_immutable(logical_uri, b"different")


def test_s3_delete_requires_expected_identity() -> None:
    store = _store(FakeS3Client())
    stored = store.put_bytes("tpaa-parquet://metrics/part.parquet", b"parquet")
    with pytest.raises(ObjectStoreError, match="hash changed"):
        store.delete_object(stored.logical_uri, expected_sha256="0" * 64)
    assert store.delete_object(
        stored.logical_uri,
        expected_sha256=stored.artifact_sha256,
    )
    assert store.delete_object(stored.logical_uri) is False


def test_s3_readiness_and_failures_do_not_expose_credentials() -> None:
    client = FakeS3Client()
    client.bucket_available = False
    store = _store(client)
    with pytest.raises(ObjectStoreError) as captured:
        store.ensure_ready()
    assert "secret" not in str(captured.value).lower()
