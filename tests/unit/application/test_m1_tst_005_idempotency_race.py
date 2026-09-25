from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from tpaa_application import M1PublicationService, M1PublishSessionCommand
from tpaa_application.m1_repository import InMemorySessionPublicationRepository

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def _command() -> M1PublishSessionCommand:
    return M1PublishSessionCommand(
        fixture_id="BF_M1_NOMINAL_V1",
        aircraft_model_id=str(uuid5(NAMESPACE_URL, "tst-005-model")),
        aircraft_instance_id=str(uuid5(NAMESPACE_URL, "tst-005-instance")),
        subject_entity_id=str(uuid5(NAMESPACE_URL, "tst-005-entity")),
        capability_dimension="TEST_EXPLICIT_CAPABILITY_DIMENSION",
        capability_type="TEST_EXPLICIT_CAPABILITY_TYPE",
        expected_version_token=0,
    )


def test_concurrent_identical_application_publish_creates_one_logical_release() -> None:
    repository = InMemorySessionPublicationRepository()
    service = M1PublicationService(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
        repository=repository,
    )
    command = _command()

    def publish(_index: int):
        return service.publish_session(
            command,
            idempotency_key="tst-005-identical-request",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(publish, range(8)))

    release_ids = {item.release_id for item in results}
    manifest_hashes = {item.manifest_hash for item in results}
    request_hashes = {item.request_hash for item in results}
    session_ids = {item.session_id for item in results}

    assert len(release_ids) == 1
    assert len(manifest_hashes) == 1
    assert len(request_hashes) == 1
    assert len(session_ids) == 1
    assert sum(item.reused is False for item in results) == 1
    assert sum(item.reused is True for item in results) == 7

    session_id = next(iter(session_ids))
    release_id = next(iter(release_ids))
    assert repository.version_token(session_id) == 1
    current = repository.current(session_id)
    assert current is not None
    assert current.release.release_id == release_id
    assert current.version_token == 1
