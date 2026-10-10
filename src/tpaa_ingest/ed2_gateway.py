"""ED-2 Joint/LVC gateway adapter behind the external-protocol boundary."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .p6_interop import (
    P6InteropArtifactRef,
    P6InteropSnapshot,
    build_p6_interop_snapshot,
)


class JointLVCGatewayError(RuntimeError):
    """Fail-closed external gateway contract error."""


@dataclass(frozen=True, slots=True)
class JointLVCGatewayAdapter:
    external_profile_id: str
    external_profile_version: str
    adapter_id: str
    adapter_version: str

    def project_fact_source(
        self,
        *,
        session_id: str,
        source_id: str,
        source_stream_id: str | None,
        artifact_refs: Sequence[P6InteropArtifactRef],
        producer_system: str,
        unit_basis: Mapping[str, str],
        time_basis: str,
        canonical_entity_refs: Sequence[str],
        applicability_status: str,
        uncertainty: Mapping[str, object],
        as_of_utc: str,
        source_available_at_utc: str,
    ) -> P6InteropSnapshot:
        if not all(
            value.strip()
            for value in (
                self.external_profile_id,
                self.external_profile_version,
                self.adapter_id,
                self.adapter_version,
            )
        ):
            raise JointLVCGatewayError("ED2_GATEWAY_PROFILE_REQUIRED")
        return build_p6_interop_snapshot(
            session_id=session_id,
            session_type="LVC",
            source_id=source_id,
            source_stream_id=source_stream_id,
            artifact_refs=artifact_refs,
            producer_system=producer_system,
            external_profile_id=self.external_profile_id,
            external_profile_version=self.external_profile_version,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            unit_basis=unit_basis,
            time_basis=time_basis,
            source_or_projection_class="FACT_SOURCE",
            payload_class="FACT_SOURCE",
            canonical_entity_refs=canonical_entity_refs,
            applicability_status=applicability_status,
            uncertainty=uncertainty,
            release_state="VALIDATED",
            as_of_utc=as_of_utc,
            source_available_at_utc=source_available_at_utc,
            lossless_phase_mapping=True,
        )

    def upper_product_payload(
        self,
        snapshot: P6InteropSnapshot,
        *,
        canonical_relation_refs: Sequence[str],
    ) -> dict[str, object]:
        if snapshot.session_type != "LVC" or not snapshot.lossless_phase_mapping:
            raise JointLVCGatewayError("ED2_GATEWAY_SNAPSHOT_INVALID")
        return {
            "external_protocol_boundary": True,
            "session_type": "LVC",
            "external_profile_id": snapshot.external_profile_id,
            "external_profile_version": snapshot.external_profile_version,
            "adapter_id": snapshot.adapter_id,
            "adapter_version": snapshot.adapter_version,
            "mapping_lossless": True,
            "fact_projection_separated": True,
            "operational_optimization": False,
            "unit_basis": dict(snapshot.unit_basis),
            "time_basis": snapshot.time_basis,
            "canonical_entity_refs": list(snapshot.canonical_entity_refs),
            "canonical_relation_refs": list(canonical_relation_refs),
            "interop_snapshot_id": snapshot.interop_snapshot_id,
            "logical_content_hash": snapshot.logical_content_hash,
        }
