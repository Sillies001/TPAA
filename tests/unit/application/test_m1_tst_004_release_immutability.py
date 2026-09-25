from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

from tpaa_application import M1PublicationService, M1PublishSessionCommand
from tpaa_application.m1_repository import InMemorySessionPublicationRepository

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def _command() -> M1PublishSessionCommand:
    return M1PublishSessionCommand(
        fixture_id="BF_M1_NOMINAL_V1",
        aircraft_model_id=str(uuid5(NAMESPACE_URL, "tst-004-model")),
        aircraft_instance_id=str(uuid5(NAMESPACE_URL, "tst-004-instance")),
        subject_entity_id=str(uuid5(NAMESPACE_URL, "tst-004-entity")),
        capability_dimension="TEST_EXPLICIT_CAPABILITY_DIMENSION",
        capability_type="TEST_EXPLICIT_CAPABILITY_TYPE",
        expected_version_token=0,
    )


def test_published_release_definition_and_context_are_immutable_snapshots() -> None:
    repository = InMemorySessionPublicationRepository()
    service = M1PublicationService(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
        repository=repository,
    )
    published = service.publish_session(_command(), idempotency_key="tst-004")
    stored = repository.get_release(published.release_id).release

    manifest_field = "manifest_hash"
    algorithm_field = "algorithm_version"
    status_field = "status"
    with pytest.raises(FrozenInstanceError):
        setattr(stored, manifest_field, "0" * 64)
    with pytest.raises(FrozenInstanceError):
        setattr(stored.definitions[0], algorithm_field, "tampered")
    with pytest.raises(FrozenInstanceError):
        setattr(stored.metric_instances[0], status_field, "INVALID")

    summary_before = service.release_summary(published.release_id)
    expected_manifest = summary_before["manifest_hash"]
    provenance = summary_before["provenance"]
    assert isinstance(provenance, dict)
    provenance["request_hash"] = "0" * 64
    summary_before["manifest_hash"] = "0" * 64

    summary_after = service.release_summary(published.release_id)
    assert summary_after["manifest_hash"] == expected_manifest
    assert summary_after["provenance"]["request_hash"] == stored.request_hash

    context_before = service.context_projection(published.release_id)
    original_status = context_before["status"]
    original_context_id = context_before["context_id"]
    context_before["status"] = "TAMPERED"

    context_after = service.context_projection(published.release_id)
    assert context_after["status"] == original_status
    assert context_after["context_id"] == original_context_id
    assert context_after == stored.context_dto()

    detail_before = service.metric_detail(published.release_id, "P1-AIR-001")
    definition_before = detail_before["definition"]
    evidence_before = detail_before["evidence"]
    assert isinstance(definition_before, dict)
    assert isinstance(evidence_before, dict)
    expected_definition_hash = definition_before["definition_hash"]
    expected_evidence_hash = evidence_before["logical_hash"]
    definition_before["definition_hash"] = "0" * 64
    evidence_before["logical_hash"] = "0" * 64

    detail_after = service.metric_detail(published.release_id, "P1-AIR-001")
    assert detail_after["definition"]["definition_hash"] == expected_definition_hash
    assert detail_after["evidence"]["logical_hash"] == expected_evidence_hash
