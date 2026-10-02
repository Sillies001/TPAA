"""M9 Batch 1 exact Joint/LVC and external interoperability substrate."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tpaa_context.p6_governance import P6AdmissionEvidence, P6AuthorityPolicy


@dataclass(frozen=True, slots=True)
class P6InteropArtifactRef:
    artifact_ref_id: str
    object_hash: str
    payload_class: str


@dataclass(frozen=True, slots=True)
class P6InteropSnapshot:
    interop_snapshot_id: str
    session_id: str
    session_type: str
    source_id: str
    source_stream_id: str | None
    artifact_refs: tuple[str, ...]
    producer_system: str
    external_profile_id: str
    external_profile_version: str
    adapter_id: str
    adapter_version: str
    unit_basis: tuple[tuple[str, str], ...]
    time_basis: str
    source_or_projection_class: str
    canonical_entity_refs: tuple[str, ...]
    object_hashes: tuple[str, ...]
    applicability_status: str
    uncertainty: dict[str, object]
    release_state: str
    as_of_utc: str
    logical_content_hash: str
    artifact_bindings: tuple[P6InteropArtifactRef, ...]
    lossless_phase_mapping: bool = True


def _identity_material(snapshot: P6InteropSnapshot) -> dict[str, object]:
    return {
        "session_id": snapshot.session_id,
        "session_type": snapshot.session_type,
        "source_id": snapshot.source_id,
        "source_stream_id": snapshot.source_stream_id,
        "artifact_bindings": [
            {
                "artifact_ref_id": item.artifact_ref_id,
                "object_hash": item.object_hash,
                "payload_class": item.payload_class,
            }
            for item in snapshot.artifact_bindings
        ],
        "producer_system": snapshot.producer_system,
        "external_profile_id": snapshot.external_profile_id,
        "external_profile_version": snapshot.external_profile_version,
        "adapter_id": snapshot.adapter_id,
        "adapter_version": snapshot.adapter_version,
        "unit_basis": dict(snapshot.unit_basis),
        "time_basis": snapshot.time_basis,
        "source_or_projection_class": snapshot.source_or_projection_class,
        "canonical_entity_refs": list(snapshot.canonical_entity_refs),
        "applicability_status": snapshot.applicability_status,
        "uncertainty": snapshot.uncertainty,
        "release_state": snapshot.release_state,
        "as_of_utc": snapshot.as_of_utc,
        "lossless_phase_mapping": snapshot.lossless_phase_mapping,
    }


def build_p6_interop_snapshot(
    *,
    session_id: str,
    session_type: str,
    source_id: str,
    source_stream_id: str | None,
    artifact_refs: Sequence[P6InteropArtifactRef],
    producer_system: str,
    external_profile_id: str,
    external_profile_version: str,
    adapter_id: str,
    adapter_version: str,
    unit_basis: Mapping[str, str],
    time_basis: str,
    source_or_projection_class: str,
    payload_class: str,
    canonical_entity_refs: Sequence[str],
    applicability_status: str,
    uncertainty: Mapping[str, object],
    release_state: str,
    as_of_utc: str,
    source_available_at_utc: str,
    lossless_phase_mapping: bool = True,
    admission_evidence: P6AdmissionEvidence | None = None,
    policy: P6AuthorityPolicy | None = None,
) -> P6InteropSnapshot:
    from tpaa_context.p6_governance import (
        P6AuthorityPolicy as RuntimeP6AuthorityPolicy,
    )
    from tpaa_context.p6_governance import (
        P6GovernanceError,
        assert_p6_claim_allowed,
        canonical_hash,
        exact_hash64,
        exact_text,
        exact_uuid,
        utc,
    )

    p = policy or RuntimeP6AuthorityPolicy.from_canonical()
    exact_uuid(session_id, field="session_id", policy=p)
    if session_type not in p.session_types:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INTEROP_PROFILE_REQUIRED",
            f"session_type={session_type!r}",
        )
    exact_uuid(source_id, field="source_id", policy=p)
    if source_stream_id is not None:
        exact_uuid(source_stream_id, field="source_stream_id", policy=p)
    exact_text(producer_system, field="producer_system", policy=p)
    exact_text(external_profile_id, field="external_profile_id", policy=p)
    exact_text(
        external_profile_version,
        field="external_profile_version",
        policy=p,
    )
    exact_text(adapter_id, field="adapter_id", policy=p)
    exact_text(adapter_version, field="adapter_version", policy=p)
    exact_text(time_basis, field="time_basis", policy=p)
    exact_text(release_state, field="release_state", policy=p)

    if source_or_projection_class not in {"FACT_SOURCE", "P6_PROJECTION"}:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_FACT_PROJECTION_CONFLATION",
            source_or_projection_class,
        )
    if payload_class != source_or_projection_class:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_FACT_PROJECTION_CONFLATION",
            f"declared={source_or_projection_class} payload={payload_class}",
        )
    if not lossless_phase_mapping:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INTEROP_LOSSY_MAPPING",
            "phase/unit mapping is not lossless",
        )
    if applicability_status not in p.applicability_states:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_APPLICABILITY_REQUIRED",
            f"applicability_status={applicability_status!r}",
        )

    as_of = utc(as_of_utc, field="as_of_utc")
    available_at = utc(source_available_at_utc, field="source_available_at_utc")
    if available_at > as_of:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_FUTURE_INFORMATION",
            "interop source became available after as_of",
        )

    if not artifact_refs:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INTEROP_PROFILE_REQUIRED",
            "at least one exact artifact ref is required",
        )
    normalized_artifacts: list[P6InteropArtifactRef] = []
    for item in artifact_refs:
        exact_uuid(item.artifact_ref_id, field="artifact_ref_id", policy=p)
        exact_hash64(item.object_hash, field="object_hash")
        if item.payload_class != source_or_projection_class:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_FACT_PROJECTION_CONFLATION",
                item.artifact_ref_id,
            )
        normalized_artifacts.append(item)
    artifacts = tuple(
        sorted(normalized_artifacts, key=lambda item: item.artifact_ref_id)
    )

    if not unit_basis:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INTEROP_PROFILE_REQUIRED",
            "unit_basis",
        )
    normalized_units = tuple(
        sorted(
            (
                exact_text(key, field="unit_basis.key", policy=p),
                exact_text(value, field="unit_basis.value", policy=p),
            )
            for key, value in unit_basis.items()
        )
    )
    normalized_entities = tuple(
        sorted(
            {
                exact_text(item, field="canonical_entity_ref", policy=p)
                for item in canonical_entity_refs
            }
        )
    )
    uncertainty_object = dict(uncertainty)
    canonical_hash(uncertainty_object)

    if source_or_projection_class == "P6_PROJECTION" and release_state == "RELEASED":
        assert_p6_claim_allowed("P6", evidence=admission_evidence, policy=p)

    snapshot = P6InteropSnapshot(
        interop_snapshot_id="",
        session_id=session_id,
        session_type=session_type,
        source_id=source_id,
        source_stream_id=source_stream_id,
        artifact_refs=tuple(item.artifact_ref_id for item in artifacts),
        producer_system=producer_system,
        external_profile_id=external_profile_id,
        external_profile_version=external_profile_version,
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        unit_basis=normalized_units,
        time_basis=time_basis,
        source_or_projection_class=source_or_projection_class,
        canonical_entity_refs=normalized_entities,
        object_hashes=tuple(item.object_hash for item in artifacts),
        applicability_status=applicability_status,
        uncertainty=uncertainty_object,
        release_state=release_state,
        as_of_utc=as_of_utc,
        logical_content_hash="",
        artifact_bindings=artifacts,
        lossless_phase_mapping=lossless_phase_mapping,
    )
    digest = canonical_hash(_identity_material(snapshot))
    return P6InteropSnapshot(
        interop_snapshot_id=f"P6_INTEROP_SHA256:{digest}",
        session_id=snapshot.session_id,
        session_type=snapshot.session_type,
        source_id=snapshot.source_id,
        source_stream_id=snapshot.source_stream_id,
        artifact_refs=snapshot.artifact_refs,
        producer_system=snapshot.producer_system,
        external_profile_id=snapshot.external_profile_id,
        external_profile_version=snapshot.external_profile_version,
        adapter_id=snapshot.adapter_id,
        adapter_version=snapshot.adapter_version,
        unit_basis=snapshot.unit_basis,
        time_basis=snapshot.time_basis,
        source_or_projection_class=snapshot.source_or_projection_class,
        canonical_entity_refs=snapshot.canonical_entity_refs,
        object_hashes=snapshot.object_hashes,
        applicability_status=snapshot.applicability_status,
        uncertainty=snapshot.uncertainty,
        release_state=snapshot.release_state,
        as_of_utc=snapshot.as_of_utc,
        logical_content_hash=digest,
        artifact_bindings=snapshot.artifact_bindings,
        lossless_phase_mapping=snapshot.lossless_phase_mapping,
    )


def assert_p6_interop_snapshot_identity(snapshot: P6InteropSnapshot) -> None:
    from tpaa_context.p6_governance import P6GovernanceError, canonical_hash

    digest = canonical_hash(_identity_material(snapshot))
    if (
        not snapshot.lossless_phase_mapping
        or snapshot.logical_content_hash != digest
        or snapshot.interop_snapshot_id != f"P6_INTEROP_SHA256:{digest}"
    ):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INTEROP_PROFILE_REQUIRED",
            "P6 interoperability snapshot identity drift",
        )
