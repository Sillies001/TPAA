from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from tpaa_application import (
    M1PublicationService,
    M1PublishSessionCommand,
)
from tpaa_storage.publication import InMemorySessionPublicationRepository

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def _command(expected_version_token: int) -> M1PublishSessionCommand:
    return M1PublishSessionCommand(
        fixture_id="BF_M1_NOMINAL_V1",
        aircraft_model_id=str(uuid5(NAMESPACE_URL, "m1-service-model")),
        aircraft_instance_id=str(uuid5(NAMESPACE_URL, "m1-service-instance")),
        subject_entity_id=str(uuid5(NAMESPACE_URL, "m1-service-entity")),
        capability_dimension="TEST_EXPLICIT_CAPABILITY_DIMENSION",
        capability_type="TEST_EXPLICIT_CAPABILITY_TYPE",
        expected_version_token=expected_version_token,
    )


def test_publish_retry_and_historical_replay_remain_release_bound() -> None:
    repository = InMemorySessionPublicationRepository()
    service = M1PublicationService(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
        repository=repository,
    )

    first = service.publish_session(_command(0), idempotency_key="first")
    retry = service.publish_session(_command(0), idempotency_key="first")

    assert first.reused is False
    assert retry.reused is True
    assert retry.release_id == first.release_id
    assert retry.request_hash == first.request_hash

    first_summary = service.release_summary(first.release_id)
    first_manifest = first_summary["manifest_hash"]
    first_replay = service.replay(first.release_id)
    assert first_replay["exact_logical_products_equal"] is True
    assert first_replay["current_latest_fallback_used"] is False

    second = service.publish_session(_command(1), idempotency_key="second")
    assert second.reused is False
    assert second.release_id != first.release_id

    current = repository.current(first.session_id)
    assert current is not None
    assert current.release.release_id == second.release_id

    historical = service.release_summary(first.release_id)
    assert historical["manifest_hash"] == first_manifest
    assert service.replay(first.release_id)["exact_logical_products_equal"] is True


def test_range_query_is_explicit_and_bounded() -> None:
    service = M1PublicationService(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
        repository=InMemorySessionPublicationRepository(),
    )
    published = service.publish_session(_command(0), idempotency_key="range")
    topology = service.session_episode_stage_projection(published.release_id)
    start = int(topology["session"]["start_session_time_us"])
    end = int(topology["session"]["end_session_time_us"])

    payload = service.series_range(
        published.release_id,
        start_session_time_us=start,
        end_session_time_us=end,
        limit=3,
    )

    assert payload["limit"] == 3
    assert payload["returned"] <= 3
    assert len(payload["rows"]) <= 3
    assert all(isinstance(row["session_time_us"], str) for row in payload["rows"])
