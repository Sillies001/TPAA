from __future__ import annotations

import os
from importlib import import_module

import pytest

from tpaa_storage import LocalSealedObjectFlow, S3ObjectStore


def test_s3_adapter_over_real_http_endpoint() -> None:
    endpoint = os.environ.get("TPAA_TEST_S3_ENDPOINT")
    if not endpoint:
        pytest.skip("TPAA_TEST_S3_ENDPOINT is not configured")
    access_key = os.environ.get("TPAA_TEST_S3_ACCESS_KEY", "tpaa-test-access")
    secret_key = os.environ.get("TPAA_TEST_S3_SECRET_KEY", "tpaa-test-secret")
    bucket = os.environ.get("TPAA_TEST_S3_BUCKET", "tpaa-http-integration")
    boto3 = import_module("boto3")
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    client.create_bucket(Bucket=bucket)
    store = S3ObjectStore(
        bucket=bucket,
        prefix="qualification",
        client=client,
    )

    store.ensure_ready()
    flow = LocalSealedObjectFlow(store)
    staged = flow.stage(
        sealed_uri="tpaa-object://products/http-integration.bin",
        data=b"real-http-s3-round-trip",
        operation_id="http-integration",
    )
    sealed = flow.seal(staged)

    assert store.verify(sealed)
    assert store.read_bytes(sealed.logical_uri) == b"real-http-s3-round-trip"
    assert store.list_objects("tpaa-object://products") == (sealed,)
    assert all("staging" not in item.logical_uri for item in store.inventory())
