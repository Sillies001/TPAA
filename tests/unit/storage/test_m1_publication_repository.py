from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import NAMESPACE_URL, uuid5

import pytest

from tpaa_observation import SessionRelease
from tpaa_application.m1_repository import (
    InMemorySessionPublicationRepository,
    PublishCASConflict,
)


def _release(
    *,
    label: str,
    release_no: int = 1,
    parent_release_id: str | None = None,
) -> SessionRelease:
    release_id = str(uuid5(NAMESPACE_URL, f"release:{label}"))
    session_id = str(uuid5(NAMESPACE_URL, "session"))
    context_id = str(uuid5(NAMESPACE_URL, "context"))
    request_hash = "%064x" % (release_no + 10)
    manifest_hash = "%064x" % (release_no + 20)
    fixed_hash = "a" * 64
    return SessionRelease(
        release_id=release_id,
        release_no=release_no,
        parent_release_id=parent_release_id,
        request_hash=request_hash,
        scope_type="SESSION",
        scope_key=session_id,
        fixture_id="TEST_FIXTURE",
        session_id=session_id,
        context_id=context_id,
        context_version="M1-BASIC-CONTEXT-1.0.0",
        context_binding_hash=fixed_hash,
        catalog_version="1.14.0",
        catalog_hash="b" * 64,
        world_product_id=str(uuid5(NAMESPACE_URL, f"world:{label}")),
        world_logical_hash="c" * 64,
        definitions=(),
        evidence_sets=(),
        metric_instances=(),
        observations=(),
        manifest_hash=manifest_hash,
    )


def test_concurrent_identical_publish_has_one_logical_current_release() -> None:
    repo = InMemorySessionPublicationRepository()
    release = _release(label="one")

    def publish() -> bool:
        return repo.publish(
            release,
            idempotency_key="same-request",
            expected_version_token=0,
        ).reused

    with ThreadPoolExecutor(max_workers=8) as pool:
        reused = list(pool.map(lambda _: publish(), range(8)))

    assert reused.count(False) == 1
    assert reused.count(True) == 7
    assert repo.version_token(release.session_id) == 1
    assert repo.current(release.session_id) is not None
    assert repo.current(release.session_id).release.release_id == release.release_id


def test_historical_release_is_immutable_after_new_current_publish() -> None:
    repo = InMemorySessionPublicationRepository()
    first = _release(label="one")
    repo.publish(first, idempotency_key="first", expected_version_token=0)

    second = _release(
        label="two",
        release_no=2,
        parent_release_id=first.release_id,
    )
    repo.publish(second, idempotency_key="second", expected_version_token=1)

    assert repo.current(first.session_id).release.release_id == second.release_id
    historical = repo.get_release(first.release_id)
    assert historical.release == first
    assert historical.release.manifest_hash == first.manifest_hash


def test_stale_pointer_token_is_rejected() -> None:
    repo = InMemorySessionPublicationRepository()
    first = _release(label="one")
    repo.publish(first, idempotency_key="first", expected_version_token=0)
    second = _release(label="two", release_no=2, parent_release_id=first.release_id)

    with pytest.raises(PublishCASConflict):
        repo.publish(second, idempotency_key="second", expected_version_token=0)
