from __future__ import annotations

from tpaa_ingest import JointLVCGatewayAdapter, P6InteropArtifactRef

_SESSION = "11111111-1111-4111-8111-111111111111"
_SOURCE = "22222222-2222-4222-8222-222222222222"
_STREAM = "33333333-3333-4333-8333-333333333333"
_ARTIFACT = "44444444-4444-4444-8444-444444444444"


def test_ed2_b3_joint_lvc_gateway_projects_fact_source_behind_boundary() -> None:
    adapter = JointLVCGatewayAdapter(
        external_profile_id="P6_LVC_EXCHANGE",
        external_profile_version="1.0.0",
        adapter_id="P6_LVC_ADAPTER",
        adapter_version="1.0.0",
    )
    snapshot = adapter.project_fact_source(
        session_id=_SESSION,
        source_id=_SOURCE,
        source_stream_id=_STREAM,
        artifact_refs=(
            P6InteropArtifactRef(
                artifact_ref_id=_ARTIFACT,
                object_hash="a" * 64,
                payload_class="FACT_SOURCE",
            ),
        ),
        producer_system="LVC-GATEWAY-A",
        unit_basis={"altitude": "m", "speed": "m/s"},
        time_basis="UTC",
        canonical_entity_refs=("entity:aircraft:a",),
        applicability_status="APPLICABLE",
        uncertainty={"source": "declared"},
        as_of_utc="2030-01-01T05:00:00Z",
        source_available_at_utc="2030-01-01T04:59:00Z",
    )
    assert snapshot.session_type == "LVC"
    assert snapshot.source_or_projection_class == "FACT_SOURCE"
    assert snapshot.lossless_phase_mapping is True

    payload = adapter.upper_product_payload(
        snapshot,
        canonical_relation_refs=("relation:formation:a-b",),
    )
    assert payload["external_protocol_boundary"] is True
    assert payload["mapping_lossless"] is True
    assert payload["fact_projection_separated"] is True
    assert payload["operational_optimization"] is False
