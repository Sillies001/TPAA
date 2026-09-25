from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from tpaa_context import resolve_evaluation_context
from tpaa_ingest import load_synthetic_fixture_bundle
from tpaa_metric import build_metric_context, compute_representative_metrics
from tpaa_observation import (
    AircraftPublicationIdentity,
    allocate_session_release_id,
    build_session_release,
    compare_replay,
)
from tpaa_storage.hashing import canonical_request_hash
from tpaa_world import project_minimal_p1_world

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = ROOT / "tests" / "fixtures" / "m1" / "BF_M1_NOMINAL_V1"
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def test_representative_metrics_project_to_immutable_capability_observations() -> None:
    bundle = load_synthetic_fixture_bundle(BUNDLE)
    request_hash = canonical_request_hash(
        {
            "command": "publish-session",
            "fixture_id": bundle.identity.fixture_id,
            "session_id": bundle.session.session_id,
        }
    )
    release_id = allocate_session_release_id(
        session_id=bundle.session.session_id,
        request_hash=request_hash,
    )
    world = project_minimal_p1_world(
        BUNDLE,
        authority_root=AUTHORITY,
        release_id=release_id,
    )
    metric_context = build_metric_context(BUNDLE, authority_root=AUTHORITY, world=world)
    batch = compute_representative_metrics(metric_context, world)
    resolved_context = resolve_evaluation_context(BUNDLE, authority_root=AUTHORITY)
    identity = AircraftPublicationIdentity(
        aircraft_id=world.aircraft_id,
        aircraft_model_id=str(uuid5(NAMESPACE_URL, "tpaa-test-aircraft-model")),
        aircraft_instance_id=str(uuid5(NAMESPACE_URL, "tpaa-test-aircraft-instance")),
        subject_entity_id=str(uuid5(NAMESPACE_URL, "tpaa-test-aircraft-entity")),
        capability_dimension="TEST_EXPLICIT_CAPABILITY_DIMENSION",
        capability_type="TEST_EXPLICIT_CAPABILITY_TYPE",
    )

    release = build_session_release(
        release_id=release_id,
        request_hash=request_hash,
        release_no=1,
        parent_release_id=None,
        context=metric_context,
        context_version=resolved_context.context_version,
        world=world,
        batch=batch,
        identity=identity,
    )

    assert release.session_id == world.session_id
    assert release.context_id == resolved_context.context_id
    assert release.context_version == resolved_context.context_version
    assert release.catalog_hash == metric_context.catalog_sha256
    assert release.world_logical_hash == world.logical_content_hash
    assert len(release.definitions) == 5
    assert len(release.metric_instances) == 5
    assert len(release.evidence_sets) == 5
    assert len(release.observations) == 5
    assert all(item.publication_route == "CAPABILITY_OBSERVATION" for item in release.definitions)

    dto_by_code = {item.metric_code: item.dto() for item in release.observations}
    assert tuple(dto_by_code) == (
        "P1-AIR-001",
        "P1-AIR-002",
        "P1-AIR-003",
        "P1-AIR-004",
        "P1-AIR-007",
    )
    assert all(
        isinstance(dto["observation_start_session_time_us"], str)
        for dto in dto_by_code.values()
    )
    assert all(
        isinstance(dto["observation_end_session_time_us"], str)
        for dto in dto_by_code.values()
    )
    assert dto_by_code["P1-AIR-007"]["structured_output_schema_id"] == "STRUCT_P1_AIR_007_V1"
    assert isinstance(dto_by_code["P1-AIR-007"]["value"], dict)

    replay = compare_replay(
        release,
        context=metric_context,
        context_version=resolved_context.context_version,
        world=world,
        batch=batch,
    )
    assert replay.exact_logical_products_equal is True
