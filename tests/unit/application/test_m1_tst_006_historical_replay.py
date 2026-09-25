from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from tpaa_application import M1PublicationService, M1PublishSessionCommand
from tpaa_application.m1_repository import InMemorySessionPublicationRepository

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def _command(token: int, capability_type: str) -> M1PublishSessionCommand:
    return M1PublishSessionCommand(
        fixture_id="BF_M1_NOMINAL_V1",
        aircraft_model_id=str(uuid5(NAMESPACE_URL, "tst-006-model")),
        aircraft_instance_id=str(uuid5(NAMESPACE_URL, "tst-006-instance")),
        subject_entity_id=str(uuid5(NAMESPACE_URL, "tst-006-entity")),
        capability_dimension="TEST_EXPLICIT_CAPABILITY_DIMENSION",
        capability_type=capability_type,
        expected_version_token=token,
    )


def test_new_current_release_does_not_change_historical_interpretation() -> None:
    repository = InMemorySessionPublicationRepository()
    service = M1PublicationService(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
        repository=repository,
    )

    first = service.publish_session(
        _command(0, "TEST_CAPABILITY_A"),
        idempotency_key="tst-006-first",
    )
    first_summary_before = service.release_summary(first.release_id)
    first_context_before = service.context_projection(first.release_id)
    first_metric_before = service.metric_detail(first.release_id, "P1-AIR-007")
    first_evidence_before = service.metric_evidence(first.release_id, "P1-AIR-007")
    first_replay_before = service.replay(first.release_id)

    second = service.publish_session(
        _command(1, "TEST_CAPABILITY_B"),
        idempotency_key="tst-006-second",
    )
    assert second.release_id != first.release_id
    current = repository.current(first.session_id)
    assert current is not None
    assert current.release.release_id == second.release_id
    assert current.version_token == 2

    first_summary_after = service.release_summary(first.release_id)
    first_context_after = service.context_projection(first.release_id)
    first_metric_after = service.metric_detail(first.release_id, "P1-AIR-007")
    first_evidence_after = service.metric_evidence(first.release_id, "P1-AIR-007")
    first_replay_after = service.replay(first.release_id)

    assert first_summary_after == first_summary_before
    assert first_context_after == first_context_before
    assert first_metric_after == first_metric_before
    assert first_evidence_after == first_evidence_before
    assert first_replay_after == first_replay_before
    assert first_replay_after["status"] == "PASS"
    assert first_replay_after["release_status"] == "PUBLISHED"
    assert first_replay_after["current_latest_fallback_used"] is False
